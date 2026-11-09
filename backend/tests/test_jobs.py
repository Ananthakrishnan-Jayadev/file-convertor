"""JobStore: surviving restarts, cancelling, cleanup. Each test gets its own data folder."""

import sys
import time
from pathlib import Path

import pytest

from app import tools
from app.jobs import RESTARTED, JobStore


def wait(predicate, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    pytest.fail("condition not reached in time")


def start(store: JobStore, work, name="a.txt"):
    job = store.create(name, "txt", None)
    src = job.dir / "in" / name
    src.write_text("hello")
    store.submit_work(job, work, [src])
    return job


def write_result(out_dir: Path) -> Path:
    dst = out_dir / "result.txt"
    dst.write_text("done")
    return dst


def sleep_in_child(seconds: float):
    """Work that runs an external program, like LibreOffice or FFmpeg would."""
    def work(out_dir: Path) -> Path:
        tools.run([sys.executable, "-c", f"import time; time.sleep({seconds})"], timeout=60)
        return write_result(out_dir)
    return work


def test_finished_jobs_survive_a_restart(tmp_path):
    store = JobStore(tmp_path, workers=1)
    job = start(store, write_result)
    wait(lambda: job.status == "done")

    reopened = JobStore(tmp_path, workers=1).get(job.id)
    assert reopened is not None and reopened.status == "done"
    assert reopened.output_path.read_text() == "done"


def test_unfinished_jobs_fail_cleanly_after_a_restart(tmp_path):
    store = JobStore(tmp_path, workers=1)
    job = store.create("a.txt", "txt", None)  # created but never run, as if the server died

    reopened = JobStore(tmp_path, workers=1).get(job.id)
    assert reopened.status == "error" and reopened.error == RESTARTED


def test_jobs_whose_files_vanished_are_forgotten(tmp_path):
    store = JobStore(tmp_path, workers=1)
    job = start(store, write_result)
    wait(lambda: job.status == "done")
    job.output_path.unlink()

    assert JobStore(tmp_path, workers=1).get(job.id) is None


def test_cancel_kills_a_running_program(tmp_path):
    store = JobStore(tmp_path, workers=1)
    job = start(store, sleep_in_child(30))
    wait(lambda: job.status == "running")
    time.sleep(0.3)  # let the child process start

    began = time.time()
    store.cancel(job)
    assert job.status == "cancelled"
    wait(lambda: not (job.dir / "out").exists(), timeout=10)
    assert time.time() - began < 5
    assert job.output_path is None


def test_cancelled_queued_job_never_runs(tmp_path):
    ran = []
    store = JobStore(tmp_path, workers=1)
    first = start(store, sleep_in_child(1), "first.txt")
    second = start(store, lambda out: ran.append(1) or write_result(out), "second.txt")
    store.cancel(second)
    wait(lambda: first.status == "done")
    time.sleep(0.3)
    assert ran == [] and second.status == "cancelled"


def test_cancel_is_remembered_across_restart(tmp_path):
    store = JobStore(tmp_path, workers=1)
    job = start(store, sleep_in_child(30))
    store.cancel(job)
    assert JobStore(tmp_path, workers=1).get(job.id).status == "cancelled"


def test_cleanup_deletes_expired_jobs(tmp_path):
    store = JobStore(tmp_path, workers=1, ttl=1)
    job = start(store, write_result)
    wait(lambda: job.status == "done")
    job.created -= 5
    store.cleanup()
    assert store.get(job.id) is None
    assert not job.dir.exists()
    assert JobStore(tmp_path, workers=1).get(job.id) is None


def test_cleanup_leaves_running_jobs_alone(tmp_path):
    store = JobStore(tmp_path, workers=1, ttl=1)
    job = start(store, sleep_in_child(3))
    wait(lambda: job.status == "running")
    job.created -= 5
    store.cleanup()
    assert store.get(job.id) is job
    store.cancel(job)


def test_timeouts_stop_the_program():
    began = time.time()
    with pytest.raises(TimeoutError, match="took longer"):
        tools.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)
    assert time.time() - began < 5
