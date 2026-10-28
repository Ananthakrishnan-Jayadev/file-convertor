"""In-process job queue. Conversions run on a thread pool; finished files are deleted
after JOB_TTL seconds. The API only talks to JobStore, so this can later be swapped for
Celery/RQ + Redis without touching the endpoints or the frontend."""

import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .compress import shrink
from .registry import find, normalize

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("FC_DATA_DIR") or Path(tempfile.gettempdir()) / "file-conversion")
JOB_TTL = int(os.environ.get("FC_JOB_TTL", 3600))
WORKERS = int(os.environ.get("FC_WORKERS") or max(2, (os.cpu_count() or 2) // 2))


class UnsupportedConversion(ValueError):
    pass


@dataclass
class Job:
    filename: str
    target_format: str
    max_bytes: int | None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"  # queued | running | done | error
    error: str | None = None
    input_size: int = 0
    output_path: Path | None = None
    output_size: int | None = None
    target_met: bool | None = None
    note: str = ""
    created: float = field(default_factory=time.time)

    @property
    def dir(self) -> Path:
        return DATA_DIR / "jobs" / self.id

    def public(self) -> dict:
        return {
            "id": self.id,
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


def convert_file(src: Path, out_dir: Path, target_format: str) -> Path:
    src_ext = normalize(src.suffix)
    if target_format == src_ext:  # "keep format", typically just to shrink it
        dst = out_dir / src.name
        shutil.copyfile(src, dst)
        return dst
    converter = find(src_ext, target_format)
    if converter is None:
        raise UnsupportedConversion(f"Converting .{src_ext} to .{target_format} isn't supported.")
    return converter.fn(src, out_dir, target_format)


class JobStore:
    def __init__(self, workers: int = WORKERS):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="convert")
        threading.Thread(target=self._cleanup_loop, daemon=True, name="job-cleanup").start()

    def create(self, filename: str, target_format: str, max_bytes: int | None) -> Job:
        job = Job(filename=filename, target_format=target_format, max_bytes=max_bytes)
        (job.dir / "in").mkdir(parents=True)
        (job.dir / "out").mkdir()
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def submit(self, job: Job, src: Path) -> None:
        job.input_size = src.stat().st_size
        self._pool.submit(self._run, job, src)

    def discard(self, job: Job) -> None:
        with self._lock:
            self._jobs.pop(job.id, None)
        shutil.rmtree(job.dir, ignore_errors=True)

    def _run(self, job: Job, src: Path) -> None:
        job.status = "running"
        try:
            out = convert_file(src, job.dir / "out", job.target_format)
            if job.max_bytes:
                result = shrink(out, job.max_bytes)
                out, job.target_met, job.note = result.path, result.met, result.note
            job.output_path = out
            job.output_size = out.stat().st_size
            job.status = "done"
        except Exception as exc:
            log.exception("job %s failed", job.id)
            job.error = str(exc) or exc.__class__.__name__
            job.status = "error"
        finally:
            src.unlink(missing_ok=True)

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(min(300, JOB_TTL))
            cutoff = time.time() - JOB_TTL
            with self._lock:
                expired = [j for j in self._jobs.values() if j.created < cutoff and j.status in ("done", "error")]
            for job in expired:
                self.discard(job)
