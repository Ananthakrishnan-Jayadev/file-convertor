"""Size controller: shrink a converted file so it fits under a byte budget.

Each file type gets the strategy that loses the least:
- lossy images: binary-search the encoder quality, then downscale if quality alone isn't enough
- lossless images: optimise / reduce to a 256-colour palette, then downscale
- PDF: Ghostscript re-render with progressively lower image resolution
- Office/ODF/EPUB (zip containers): recompress the embedded pictures
- anything else (CSV, TXT, JSON...): can only be shrunk losslessly, so we zip it
When the target can't be reached we keep the smallest result and say so.
"""

import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .converters import images
from .registry import normalize

MIN_QUALITY = 30
MAX_QUALITY = 92
MAX_RESIZE_STEPS = 12
MIN_SIDE = 16

GHOSTSCRIPT = os.environ.get("GS_BIN") or shutil.which("gs")
# (PDFSETTINGS preset, image DPI), tried from best to worst quality.
PDF_LEVELS = [("/printer", 220), ("/ebook", 150), ("/screen", 110), ("/screen", 72), ("/screen", 50)]

CONTAINERS = {"docx", "pptx", "xlsx", "odt", "odp", "ods", "epub"}
# (JPEG quality, scale) applied to pictures inside a container, from gentle to harsh.
CONTAINER_LEVELS = [(80, 1.0), (65, 0.8), (50, 0.6), (40, 0.45), (30, 0.3)]
MEDIA_MIN_BYTES = 20_000  # small pictures aren't worth touching


@dataclass
class Shrunk:
    path: Path
    met: bool
    note: str = ""


def human(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def shrink(path: Path, target: int) -> Shrunk:
    """Shrink `path` in place (or replace it with a .zip) to at most `target` bytes."""
    if path.stat().st_size <= target:
        return Shrunk(path, True)

    ext = normalize(path.suffix)
    note = ""
    if ext in images.IMAGE_OUT - {"pdf"}:
        _keep_if_smaller(path, _shrink_image(path, ext, target))
    elif ext == "pdf":
        if GHOSTSCRIPT:
            _keep_if_smaller(path, _shrink_pdf(path, target))
        else:
            note = "PDF compression needs Ghostscript, which isn't installed on the server."
    elif ext in CONTAINERS:
        _keep_if_smaller(path, _shrink_container(path, target))
    elif ext == "zip":
        note = "Multi-file results are zipped as they are; the size limit isn't applied to them."
    else:
        path, note = _zip_fallback(path)

    size = path.stat().st_size
    if size <= target:
        return Shrunk(path, True, note)
    reached = f"The smallest we could get was {human(size)}, above the {human(target)} limit."
    return Shrunk(path, False, f"{note} {reached}".strip())


def _keep_if_smaller(path: Path, data: bytes | None) -> None:
    if data is not None and len(data) < path.stat().st_size:
        path.write_bytes(data)


# --- images -------------------------------------------------------------------------


def _shrink_image(path: Path, ext: str, target: int) -> bytes:
    im = images.prepare(images.load(path), ext)
    best: bytes | None = None
    scale = 1.0
    for _ in range(MAX_RESIZE_STEPS):
        w, h = round(im.width * scale), round(im.height * scale)
        if min(w, h) < MIN_SIDE:
            break
        candidate = im if scale == 1.0 else im.resize((w, h), Image.Resampling.LANCZOS)
        data = _encode_under(candidate, ext, target)
        if best is None or len(data) < len(best):
            best = data
        if len(data) <= target:
            break
        # File size roughly follows pixel count, so scale the sides by sqrt of the overshoot,
        # with a little margin, and always shrink by at least 10%.
        scale *= max(0.3, min(0.9, (target / len(data)) ** 0.5 * 0.95))
    return best if best is not None else path.read_bytes()


def _encode_under(im: Image.Image, ext: str, target: int) -> bytes:
    """Best-looking encoding of `im` that fits `target`, or the smallest one we tried."""
    if ext in images.LOSSY:
        lo, hi, fit = MIN_QUALITY, MAX_QUALITY, None
        while lo <= hi:
            q = (lo + hi) // 2
            data = images.encode(im, ext, q)
            if len(data) <= target:
                fit, lo = data, q + 1
            else:
                hi = q - 1
        return fit or images.encode(im, ext, MIN_QUALITY)

    data = images.encode(im, ext)
    if len(data) <= target or ext not in ("png", "gif", "tiff", "bmp"):
        return data
    # Lossless formats: a 256-colour palette usually halves the size with little visible change.
    # Only PNG and GIF keep transparency through a palette, so the others get RGB only.
    if im.mode == "RGB" or (im.mode == "RGBA" and ext in ("png", "gif")):
        quantized = im.quantize(256, method=Image.Quantize.FASTOCTREE)
        return min(data, images.encode(quantized, ext), key=len)
    return data


# --- PDF ----------------------------------------------------------------------------


def _shrink_pdf(path: Path, target: int) -> bytes | None:
    best: bytes | None = None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.pdf"
        for preset, dpi in PDF_LEVELS:
            cmd = [
                GHOSTSCRIPT, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dNOPAUSE", "-dBATCH",
                "-dQUIET", "-dSAFER", f"-dPDFSETTINGS={preset}",
                "-dDownsampleColorImages=true", "-dDownsampleGrayImages=true", "-dDownsampleMonoImages=true",
                f"-dColorImageResolution={dpi}", f"-dGrayImageResolution={dpi}",
                f"-dMonoImageResolution={dpi * 2}",
                f"-sOutputFile={out}", str(path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=300, check=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
            data = out.read_bytes()
            if best is None or len(data) < len(best):
                best = data
            if len(data) <= target:
                break
    return best


# --- zip containers (DOCX, PPTX, XLSX, ODF, EPUB) ------------------------------------


def _shrink_container(path: Path, target: int) -> bytes | None:
    best: bytes | None = None
    for quality, scale in CONTAINER_LEVELS:
        data = _repack(path, quality, scale)
        if best is None or len(data) < len(best):
            best = data
        if len(data) <= target:
            break
    return best


def _repack(path: Path, quality: int, scale: float) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(buf, "w") as dst:
        for info in src.infolist():
            data = src.read(info)
            if len(data) >= MEDIA_MIN_BYTES:
                data = _recompress_picture(info.filename, data, quality, scale)
            # ODF and EPUB require `mimetype` to be the first entry and stored uncompressed.
            if info.filename == "mimetype":
                dst.writestr(info, data, compress_type=zipfile.ZIP_STORED)
            else:
                dst.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


def _recompress_picture(name: str, data: bytes, quality: int, scale: float) -> bytes:
    ext = normalize(Path(name).suffix)
    if ext not in ("jpg", "png"):
        return data
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return data
    if scale < 1.0:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                       Image.Resampling.LANCZOS)
    # Keep the original format and file name: the document's XML refers to it.
    if ext == "jpg":
        new = images.encode(images.prepare(im, "jpg"), "jpg", quality)
    else:
        if im.mode in ("RGB", "RGBA"):
            im = im.quantize(256, method=Image.Quantize.FASTOCTREE)
        new = images.encode(im, "png")
    return new if len(new) < len(data) else data


# --- everything else ----------------------------------------------------------------


def _zip_fallback(path: Path) -> tuple[Path, str]:
    zipped = path.with_name(path.name + ".zip")
    with zipfile.ZipFile(zipped, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(path, path.name)
    if zipped.stat().st_size < path.stat().st_size:
        path.unlink()
        return zipped, "This file type can't be shrunk without losing data, so it was packed into a .zip."
    zipped.unlink()
    return path, "This file type can't be shrunk without losing data."
