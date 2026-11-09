"""Job queue. Work runs on a thread pool; job records are kept in SQLite so they survive a
server restart, and finished files are deleted after JOB_TTL seconds. The API only talks to
JobStore, so this can later be swapped for Celery/RQ + Redis without touching the endpoints."""

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import tools
from .compress import shrink
from .converters import images
from .registry import find, normalize

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("FC_DATA_DIR") or Path(tempfile.gettempdir()) / "file-conversion")
JOB_TTL = int(os.environ.get("FC_JOB_TTL", 3600))
WORKERS = int(os.environ.get("FC_WORKERS") or max(2, (os.cpu_count() or 2) // 2))

ACTIVE = ("queued", "running")
FINISHED = ("done", "error", "cancelled")
RESTARTED = "The server restarted before this finished. Please try again."


class UnsupportedConversion(ValueError):
    pass


# A unit of work: given the job's output folder, produce the result file and return its path.
Work = Callable[[Path], Path]


@dataclass
class Job:
    filename: str
    target_format: str
    max_bytes: int | None
    operation: str = "convert"  # convert | combine | split
    quality_cap: int | None = None  # a quality the user picked; the size limit never goes above it
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"  # queued | running | done | error | cancelled
    error: str | None = None
    input_size: int = 0
    output_path: Path | None = None
    output_size: int | None = None
    target_met: bool | None = None
    note: str = ""
    created: float = field(default_factory=time.time)
    root: Path = field(default=DATA_DIR, repr=False)

    @property
    def dir(self) -> Path:
        return self.root / "jobs" / self.id

    def public(self) -> dict:
        return {
            "id": self.id,
            "operation": self.operation,
            "filename": self.filename,
            "target_format": self.target_format,
            "max_bytes": self.max_bytes,
            "status": self.status,
            "error": self.error,
            "input_size": self.input_size,
            "output_name": self.output_path.name if self.output_path else None,
            "output_size": self.output_size,
            "target_met": self.target_met,
            "note": self.note,
        }

    def to_row(self) -> str:
        data = {k: v for k, v in self.__dict__.items() if k != "root"}
        data["output_path"] = str(self.output_path) if self.output_path else None
        return json.dumps(data)

    @classmethod
    def from_row(cls, row: str, root: Path) -> "Job":
        data = json.loads(row)
        data["output_path"] = Path(data["output_path"]) if data.get("output_path") else None
        return cls(**data, root=root)


def convert_file(src: Path, out_dir: Path, target_format: str, options: images.ImageOptions | None = None) -> Path:
    src_ext = normalize(src.suffix)
    if options is not None and not options.is_default():
        # Image edits always re-encode, even when the format stays the same.
        return images.convert_image(src, out_dir, target_format, options)
    if target_format == src_ext:  # "keep format", typically just to shrink it
        dst = out_dir / src.name
        shutil.copyfile(src, dst)
        return dst
    converter = find(src_ext, target_format)
    if converter is None:
        raise UnsupportedConversion(f"Converting .{src_ext} to .{target_format} isn't supported.")
    return converter.fn(src, out_dir, target_format)


class JobStore:
    def __init__(self, data_dir: Path = DATA_DIR, workers: int = WORKERS, ttl: int = JOB_TTL):
        self.data_dir = data_dir
        self.ttl = ttl
        self._jobs: dict[str, Job] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(data_dir / "jobs.sqlite3", check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self._load()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="convert")
        threading.Thread(target=self._cleanup_loop, daemon=True, name="job-cleanup").start()

    # --- persistence ---------------------------------------------------------------

    def _load(self) -> None:
        """Bring back jobs from before a restart. Unfinished ones can't resume, so they're
        marked as failed; finished ones whose files are gone are dropped."""
        for (row,) in self._db.execute("SELECT data FROM jobs").fetchall():
            job = Job.from_row(row, self.data_dir)
            if job.status in ACTIVE:
                job.status, job.error = "error", RESTARTED
                shutil.rmtree(job.dir / "in", ignore_errors=True)
            if job.status == "done" and not (job.output_path and job.output_path.exists()):
                self._delete_row(job.id)
                continue
            self._jobs[job.id] = job
            self._save(job)

    def _save(self, job: Job) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO jobs (id, data) VALUES (?, ?)", (job.id, job.to_row()))
            self._db.commit()

    def _delete_row(self, job_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self._db.commit()

    # --- jobs ----------------------------------------------------------------------

    def create(self, filename: str, target_format: str, max_bytes: int | None,
               operation: str = "convert", quality_cap: int | None = None) -> Job:
        job = Job(filename=filename, target_format=target_format, max_bytes=max_bytes,
                  operation=operation, quality_cap=quality_cap, root=self.data_dir)
        (job.dir / "in").mkdir(parents=True)
        (job.dir / "out").mkdir()
        with self._lock:
            self._jobs[job.id] = job
        self._save(job)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def submit(self, job: Job, src: Path, options: images.ImageOptions | None = None) -> None:
        """Convert one uploaded file to the job's target format."""
        self.submit_work(job, lambda out_dir: convert_file(src, out_dir, job.target_format, options), [src])

    def submit_work(self, job: Job, work: Work, inputs: list[Path]) -> None:
        """Run any task; `inputs` are the uploaded files, deleted once the task finishes."""
        job.input_size = sum(p.stat().st_size for p in inputs)
        self._cancel[job.id] = threading.Event()
        self._save(job)
        self._pool.submit(self._run, job, work, inputs)

    def cancel(self, job: Job) -> None:
        """Stop a queued or running job. External programs are killed right away; pure-Python
        steps stop at their next checkpoint. The record stays, marked cancelled."""
        if job.status not in ACTIVE:
            return
        if event := self._cancel.get(job.id):
            event.set()
        job.status, job.error = "cancelled", None
        self._save(job)

    def discard(self, job: Job) -> None:
        if job.status in ACTIVE:
            self.cancel(job)
        with self._lock:
            self._jobs.pop(job.id, None)
        self._cancel.pop(job.id, None)
        self._delete_row(job.id)
        shutil.rmtree(job.dir, ignore_errors=True)

    def _run(self, job: Job, work: Work, inputs: list[Path]) -> None:
        event = self._cancel.get(job.id)
        if job.status == "cancelled" or event is None:
            self._finish_cancelled(job, inputs)
            return
        job.status = "running"
        self._save(job)
        tools.set_cancel_event(event)
        try:
            out = work(job.dir / "out")
            tools.check_cancelled()
            if job.max_bytes:
                result = shrink(out, job.max_bytes, max_quality=job.quality_cap)
                out, job.target_met, job.note = result.path, result.met, result.note
            tools.check_cancelled()
            job.output_path = out
            job.output_size = out.stat().st_size
            job.status = "done"
        except tools.Cancelled:
            pass
        except Exception as exc:
            if job.status != "cancelled":
                log.exception("job %s failed", job.id)
                job.error = str(exc) or exc.__class__.__name__
                job.status = "error"
        finally:
            tools.set_cancel_event(None)
            self._cancel.pop(job.id, None)
            for p in inputs:
                p.unlink(missing_ok=True)
        if job.status == "cancelled":
            self._finish_cancelled(job, inputs)
        else:
            self._save(job)

    def _finish_cancelled(self, job: Job, inputs: list[Path]) -> None:
        for p in inputs:
            p.unlink(missing_ok=True)
        shutil.rmtree(job.dir / "out", ignore_errors=True)
        job.output_path = job.output_size = None
        self._save(job)

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(max(1, min(300, self.ttl)))
            self.cleanup()

    def cleanup(self) -> None:
        cutoff = time.time() - self.ttl
        with self._lock:
            expired = [j for j in self._jobs.values() if j.created < cutoff and j.status in FINISHED]
        for job in expired:
            self.discard(job)
