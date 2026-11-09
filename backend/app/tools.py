"""External programs (LibreOffice, Ghostscript, FFmpeg): finding them on Linux, macOS and
Windows, and running them so a job can be cancelled or time out.

Lookup order: explicit env var, then PATH, then each platform's usual install location.
Lookups return None when the program isn't installed; callers report that to the user.
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from functools import cache
from pathlib import Path


class Cancelled(Exception):
    """The job was cancelled while this step was running."""


# Each worker thread runs one job at a time; the job's cancel flag is stored per thread.
_local = threading.local()


def set_cancel_event(event: threading.Event | None) -> None:
    _local.cancel = event


def check_cancelled() -> None:
    """Call between steps of long pure-Python work to stop promptly after a cancel."""
    event = getattr(_local, "cancel", None)
    if event is not None and event.is_set():
        raise Cancelled()


def run(cmd: list[str], timeout: float, cwd: Path | str | None = None) -> tuple[int, str]:
    """Run a program, killing it if the job is cancelled or it exceeds `timeout` seconds.
    Returns (exit code, combined output)."""
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        while True:
            try:
                proc.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                cancelled = getattr(_local, "cancel", None) is not None and _local.cancel.is_set()
                if cancelled or time.monotonic() > deadline:
                    proc.kill()
                    proc.wait()
                    if cancelled:
                        raise Cancelled() from None
                    raise TimeoutError(
                        f"{Path(cmd[0]).stem} took longer than {round(timeout / 60)} minutes and was stopped."
                    ) from None
        log.seek(0)
        return proc.returncode, log.read().decode(errors="replace")


def _gs_version(exe: str) -> tuple[int, ...]:
    # ...\gs\gs10.04.0\bin\gswin64c.exe -> (10, 4, 0); compare numerically so 10.x beats 9.x
    folder = os.path.basename(os.path.dirname(os.path.dirname(exe)))
    return tuple(int(n) for n in re.findall(r"\d+", folder))


def _first_existing(paths: list[str]) -> str | None:
    return next((p for p in paths if p and os.path.isfile(p)), None)


@cache
def soffice() -> str | None:
    if env := os.environ.get("SOFFICE_BIN"):
        return env
    if sys.platform == "win32":
        # soffice.com waits for the conversion to finish; soffice.exe returns immediately.
        program_dirs = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        return shutil.which("soffice.com") or _first_existing(
            [os.path.join(d, "LibreOffice", "program", "soffice.com") for d in program_dirs]
        )
    if sys.platform == "darwin":
        return shutil.which("soffice") or _first_existing(["/Applications/LibreOffice.app/Contents/MacOS/soffice"])
    return shutil.which("soffice") or shutil.which("libreoffice")


@cache
def ghostscript() -> str | None:
    if env := os.environ.get("GS_BIN"):
        return env
    if sys.platform == "win32":
        found = shutil.which("gswin64c") or shutil.which("gswin32c")
        if found:
            return found
        # The installer puts each version in its own folder, e.g. C:\Program Files\gs\gs10.04.0\bin
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        found = glob.glob(os.path.join(program_files, "gs", "gs*", "bin", "gswin64c.exe"))
        return max(found, key=_gs_version, default=None)
    return shutil.which("gs")


@cache
def ffmpeg() -> str | None:
    if env := os.environ.get("FFMPEG_BIN"):
        return env
    if found := shutil.which("ffmpeg"):
        return found
    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        return _first_existing([r"C:\ffmpeg\bin\ffmpeg.exe", os.path.join(program_files, "ffmpeg", "bin", "ffmpeg.exe")])
    # Homebrew's folders aren't always on PATH for apps started outside a terminal.
    return _first_existing(["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])


@cache
def ffprobe() -> str | None:
    """ffprobe ships next to ffmpeg in every distribution."""
    if env := os.environ.get("FFPROBE_BIN"):
        return env
    if found := shutil.which("ffprobe"):
        return found
    if exe := ffmpeg():
        sibling = Path(exe).with_name("ffprobe" + Path(exe).suffix)
        return str(sibling) if sibling.is_file() else None
    return None
