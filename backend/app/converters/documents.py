"""Office documents via headless LibreOffice, plus Markdown via an HTML step."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown

from .. import tools
from ..registry import register

TIMEOUT = 180

# --convert-to arguments with explicit export filters, so LibreOffice never has to guess.
_WRITER = {
    "docx": "docx:MS Word 2007 XML",
    "doc": "doc:MS Word 97",
    "odt": "odt:writer8",
    "rtf": "rtf:Rich Text Format",
    "txt": "txt:Text (encoded):UTF8",
    "html": "html:HTML (StarWriter)",
    "pdf": "pdf:writer_pdf_Export",
}
_IMPRESS = {
    "pptx": "pptx:Impress MS PowerPoint 2007 XML",
    "ppt": "ppt:MS PowerPoint 97",
    "odp": "odp:impress8",
    "pdf": "pdf:impress_pdf_Export",
}
_CALC = {"pdf": "pdf:calc_pdf_Export"}


def run_soffice(src: Path, out_dir: Path, fmt: str, filters: dict[str, str]) -> Path:
    soffice = tools.soffice()
    if soffice is None:
        raise RuntimeError("This conversion needs LibreOffice, which isn't installed on the server.")
    # Each run gets its own throwaway profile; otherwise parallel conversions collide
    # on LibreOffice's profile lock and silently produce nothing. On Windows LibreOffice can
    # hold files open for a moment after exiting, so cleanup errors are ignored.
    with tempfile.TemporaryDirectory(prefix="lo-profile-", ignore_cleanup_errors=True) as profile, \
            tempfile.TemporaryDirectory(prefix="lo-out-", ignore_cleanup_errors=True) as tmp_out:
        # as_uri() gives file:///C:/... on Windows and file:///tmp/... elsewhere.
        cmd = [soffice, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless", "--norestore"]
        if src.suffix.lower() in (".html", ".htm"):
            cmd.append("--infilter=HTML (StarWriter)")  # open in Writer, not Writer/Web
        cmd += ["--convert-to", filters[fmt], "--outdir", tmp_out, str(src)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        produced = Path(tmp_out) / f"{src.stem}.{fmt}"
        if not produced.exists():
            detail = (proc.stderr or proc.stdout).strip()[-300:]
            raise RuntimeError(f"LibreOffice couldn't convert this file. {detail}".strip())
        dst = out_dir / produced.name
        shutil.move(produced, dst)
        return dst


@register("document", {"docx", "doc", "odt", "rtf", "txt", "html"}, set(_WRITER) | {"md"})
def convert_writer(src: Path, out_dir: Path, fmt: str) -> Path:
    if fmt == "md":
        # LibreOffice has no Markdown export; go through its HTML export.
        html = src if src.suffix.lower() in (".html", ".htm") else run_soffice(src, out_dir, "html", _WRITER)
        return _html_to_markdown(html, out_dir / f"{src.stem}.md")
    return run_soffice(src, out_dir, fmt, _WRITER)


@register("document", {"md"}, set(_WRITER))
def convert_markdown(src: Path, out_dir: Path, fmt: str) -> Path:
    body = markdown.markdown(src.read_text(encoding="utf-8-sig"), extensions=["tables", "fenced_code"])
    html = out_dir / f"{src.stem}.html"
    html.write_text(f"<!doctype html><meta charset='utf-8'><title>{src.stem}</title>{body}", encoding="utf-8")
    if fmt == "html":
        return html
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        staged = Path(tmp) / html.name
        shutil.move(html, staged)
        return run_soffice(staged, out_dir, fmt, _WRITER)


@register("presentation", {"pptx", "ppt", "odp"}, set(_IMPRESS))
def convert_slides(src: Path, out_dir: Path, fmt: str) -> Path:
    return run_soffice(src, out_dir, fmt, _IMPRESS)


@register("spreadsheet", {"xlsx", "xls", "ods", "csv"}, set(_CALC))
def convert_sheet_pdf(src: Path, out_dir: Path, fmt: str) -> Path:
    return run_soffice(src, out_dir, fmt, _CALC)


def _html_to_markdown(html: Path, dst: Path) -> Path:
    from markdownify import markdownify

    dst.write_text(markdownify(html.read_text(encoding="utf-8", errors="replace"), heading_style="ATX"),
                   encoding="utf-8")
    if html.parent == dst.parent and html != dst:
        html.unlink(missing_ok=True)
    return dst
