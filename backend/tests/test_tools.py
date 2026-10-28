"""Program lookup on each platform. Windows and macOS are simulated, so these run anywhere."""

from pathlib import Path

import pytest

from app import tools


@pytest.fixture(autouse=True)
def fresh_lookup(monkeypatch):
    monkeypatch.delenv("SOFFICE_BIN", raising=False)
    monkeypatch.delenv("GS_BIN", raising=False)
    tools.soffice.cache_clear()
    tools.ghostscript.cache_clear()
    yield
    tools.soffice.cache_clear()
    tools.ghostscript.cache_clear()


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def nothing_on_path(monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)


def test_env_vars_win(monkeypatch):
    monkeypatch.setenv("SOFFICE_BIN", "/opt/lo/soffice")
    monkeypatch.setenv("GS_BIN", "/opt/gs/gs")
    assert tools.soffice() == "/opt/lo/soffice"
    assert tools.ghostscript() == "/opt/gs/gs"


def test_linux_uses_path(monkeypatch):
    monkeypatch.setattr(tools.sys, "platform", "linux")
    monkeypatch.setattr(tools.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert tools.soffice() == "/usr/bin/soffice"
    assert tools.ghostscript() == "/usr/bin/gs"


def test_windows_finds_libreoffice_console_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(tools.sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "x86"))
    nothing_on_path(monkeypatch)
    exe = touch(tmp_path / "LibreOffice" / "program" / "soffice.com")
    assert tools.soffice() == str(exe)


def test_windows_picks_newest_ghostscript(monkeypatch, tmp_path):
    monkeypatch.setattr(tools.sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    nothing_on_path(monkeypatch)
    touch(tmp_path / "gs" / "gs9.56.1" / "bin" / "gswin64c.exe")
    newest = touch(tmp_path / "gs" / "gs10.04.0" / "bin" / "gswin64c.exe")
    assert tools.ghostscript() == str(newest)


def test_macos_finds_app_bundle(monkeypatch):
    monkeypatch.setattr(tools.sys, "platform", "darwin")
    nothing_on_path(monkeypatch)
    bundle = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    monkeypatch.setattr(tools.os.path, "isfile", lambda p: p == bundle)
    assert tools.soffice() == bundle


def test_missing_programs_return_none(monkeypatch, tmp_path):
    monkeypatch.setattr(tools.sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    nothing_on_path(monkeypatch)
    assert tools.soffice() is None
    assert tools.ghostscript() is None
