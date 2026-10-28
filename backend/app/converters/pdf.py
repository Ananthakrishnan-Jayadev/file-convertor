import zipfile
from io import BytesIO
from pathlib import Path

import pymupdf

from ..registry import register

RENDER_DPI = 150
_PIL_FORMAT = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}


@register("pdf", {"pdf"}, {"png", "jpg", "webp", "docx", "txt"})
def convert_pdf(src: Path, out_dir: Path, fmt: str) -> Path:
    if fmt == "docx":
        from pdf2docx import Converter  # slow import, only load when needed

        dst = out_dir / f"{src.stem}.docx"
        cv = Converter(str(src))
        try:
            cv.convert(str(dst))
        finally:
            cv.close()
        return dst

    with pymupdf.open(src) as doc:
        if fmt == "txt":
            dst = out_dir / f"{src.stem}.txt"
            dst.write_text("\n\f".join(page.get_text() for page in doc), encoding="utf-8")
            return dst
        pages = [(f"{src.stem}-page{i + 1}.{fmt}", _render(page, fmt)) for i, page in enumerate(doc)]

    # One image per page; several pages come back as a zip.
    if len(pages) == 1:
        dst = out_dir / pages[0][0]
        dst.write_bytes(pages[0][1])
        return dst
    dst = out_dir / f"{src.stem}-{fmt}.zip"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in pages:
            zf.writestr(name, data)
    return dst


def _render(page, fmt: str) -> bytes:
    buf = BytesIO()
    page.get_pixmap(dpi=RENDER_DPI).pil_save(buf, format=_PIL_FORMAT[fmt], quality=85)
    return buf.getvalue()
