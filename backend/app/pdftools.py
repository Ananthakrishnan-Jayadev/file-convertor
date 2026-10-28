"""Multi-file PDF operations: combine images and PDFs into one PDF, split a PDF apart."""

import re
import zipfile
from pathlib import Path

import pymupdf

from .converters import images

COMBINE_INPUTS = images.IMAGE_IN | {"pdf"}
PX_TO_PT = 72 / 96  # image pixels are laid out at 96 dpi, so a 1920px-wide photo is a 20-inch page

_RANGE = re.compile(r"^(\d*)\s*-\s*(\d*)$|^(\d+)$")


def page_count(src: Path) -> int:
    with pymupdf.open(src) as doc:
        return doc.page_count


def parse_ranges(spec: str, pages: int) -> list[tuple[int, int]]:
    """'1-3, 5, 8-' -> [(1, 3), (5, 5), (8, pages)]. Pages are 1-based and inclusive."""
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = _RANGE.match(part)
        if not m:
            raise ValueError(f"'{part}' isn't a page or range. Use numbers like 3 or 2-5.")
        if m.group(3):
            start = end = int(m.group(3))
        else:
            start = int(m.group(1)) if m.group(1) else 1
            end = int(m.group(2)) if m.group(2) else pages
        if start < 1 or end > pages:
            raise ValueError(f"'{part}' is outside this PDF, which has {pages} page{'s' if pages != 1 else ''}.")
        if start > end:
            raise ValueError(f"'{part}' runs backwards. Write the lower page number first.")
        ranges.append((start, end))
    if not ranges:
        raise ValueError("Enter at least one page or range, for example 1-3, 5.")
    return ranges


def combine(sources: list[Path], dst: Path) -> Path:
    """Append each source in order: PDFs page by page, images as one page each."""
    with pymupdf.open() as out:
        for src in sources:
            if src.suffix.lower() == ".pdf":
                with pymupdf.open(src) as doc:
                    out.insert_pdf(doc)
            else:
                _add_image_page(out, src)
        out.save(str(dst), garbage=3, deflate=True)
    return dst


def _add_image_page(doc: pymupdf.Document, src: Path) -> None:
    im = images.load(src)  # applies EXIF rotation, opens HEIC/AVIF too
    # Photos go in as JPEG (small); images with transparency as PNG (keeps the alpha).
    fmt = "png" if images.has_alpha(im) else "jpg"
    data = images.encode(images.prepare(im, fmt), fmt, 92)
    page = doc.new_page(width=im.width * PX_TO_PT, height=im.height * PX_TO_PT)
    page.insert_image(page.rect, stream=data)


def split(src: Path, out_dir: Path, ranges: list[tuple[int, int]] | None) -> Path:
    """One PDF per range (or per page when `ranges` is None). Several parts come back as a zip."""
    parts: list[tuple[str, bytes]] = []
    with pymupdf.open(src) as doc:
        for start, end in ranges or [(p, p) for p in range(1, doc.page_count + 1)]:
            with pymupdf.open() as part:
                part.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
                label = f"page{start}" if start == end else f"pages{start}-{end}"
                parts.append((f"{src.stem}-{label}.pdf", part.tobytes(garbage=3, deflate=True)))

    if len(parts) == 1:
        dst = out_dir / parts[0][0]
        dst.write_bytes(parts[0][1])
        return dst
    dst = out_dir / f"{src.stem}-split.zip"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts:
            zf.writestr(name, data)
    return dst
