"""Locate the external programs we call (LibreOffice, Ghostscript) on Linux, macOS and Windows.

Order: explicit env var, then PATH, then each platform's usual install location.
Returns None when the program isn't installed; callers report that to the user.
"""

import glob
import os
import re
import shutil
import sys
from functools import cache


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
