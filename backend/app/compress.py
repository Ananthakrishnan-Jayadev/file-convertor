"""Size controller: shrink a converted file so it fits under a byte budget.

Each file type gets the strategy that loses the least:
- lossy images: binary-search the encoder quality, then downscale if quality alone isn't enough
- lossless images: optimise / reduce to a 256-colour palette, then downscale
- PDF: Ghostscript re-render with progressively lower image resolution
- Office/ODF/EPUB (zip containers): recompress the embedded pictures
- video: two-pass encode at the bitrate that fits the limit, lowering resolution if needed
- compressed audio: re-encode at the bitrate that fits (WAV/FLAC are lossless, so they can't)
- anything else (CSV, TXT, JSON...): can only be shrunk losslessly, so we zip it
When the target can't be reached we keep the smallest result and say so.
"""

import io
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence

from . import tools
from .converters import images, media
from .registry import normalize

MIN_QUALITY = 30
MAX_QUALITY = 92
MAX_RESIZE_STEPS = 12
MIN_SIDE = 16

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


def shrink(path: Path, target: int, zip_fallback: bool = True, max_quality: int | None = None) -> Shrunk:
    """Shrink `path` in place (or replace it with a .zip) to at most `target` bytes.
    For a .zip of results (PDF pages, split parts, sheets) the limit applies to each file inside.
    `max_quality` caps the image quality search, so a quality the user picked is never raised."""
    if path.stat().st_size <= target:
        return Shrunk(path, True)

    ext = normalize(path.suffix)
    note = ""
    if ext == "gif" and _is_animated(path):
        _keep_if_smaller(path, _shrink_animated_gif(path, target))
    elif ext in images.IMAGE_OUT - {"pdf"}:
        _keep_if_smaller(path, _shrink_image(path, ext, target, max_quality or MAX_QUALITY))
    elif ext == "pdf":
        if tools.ghostscript():
            _keep_if_smaller(path, _shrink_pdf(path, target))
        else:
            note = "PDF compression needs Ghostscript, which isn't installed on the server."
    elif ext in CONTAINERS:
        _keep_if_smaller(path, _shrink_container(path, target))
    elif ext in media.VIDEO | media.AUDIO:
        if tools.ffmpeg() is None or tools.ffprobe() is None:
            note = "Audio and video compression needs FFmpeg, which isn't installed on the server."
        elif ext in media.LOSSLESS_AUDIO:
            note = f"{ext.upper()} is uncompressed audio. Convert it to MP3, AAC or OPUS to make it smaller."
        else:
            note = _shrink_media(path, ext, target)
    elif ext == "zip":
        return _shrink_zip_members(path, target)
    elif zip_fallback:
        path, note = _zip_fallback(path)
    else:
        note = "This file type can't be shrunk without losing data."

    size = path.stat().st_size
    if size <= target:
        return Shrunk(path, True, note)
    reached = f"The smallest we could get was {human(size)}, above the {human(target)} limit."
    return Shrunk(path, False, f"{note} {reached}".strip())


def _keep_if_smaller(path: Path, data: bytes | None) -> None:
    if data is not None and len(data) < path.stat().st_size:
        path.write_bytes(data)


# --- images -------------------------------------------------------------------------


def _shrink_image(path: Path, ext: str, target: int, max_quality: int) -> bytes:
    im = images.load(path)
    # The file already reflects the user's metadata choice, so keep whatever it still carries.
    meta = images.metadata(im, keep_exif=True)
    im = images.prepare(im, ext)
    best: bytes | None = None
    scale = 1.0
    for _ in range(MAX_RESIZE_STEPS):
        tools.check_cancelled()
        w, h = round(im.width * scale), round(im.height * scale)
        if min(w, h) < MIN_SIDE:
            break
        candidate = im if scale == 1.0 else im.resize((w, h), Image.Resampling.LANCZOS)
        data = _encode_under(candidate, ext, target, max_quality, meta)
        if best is None or len(data) < len(best):
            best = data
        if len(data) <= target:
            break
        # File size roughly follows pixel count, so scale the sides by sqrt of the overshoot,
        # with a little margin, and always shrink by at least 10%.
        scale *= max(0.3, min(0.9, (target / len(data)) ** 0.5 * 0.95))
    return best if best is not None else path.read_bytes()


def _encode_under(im: Image.Image, ext: str, target: int, max_quality: int, meta: dict) -> bytes:
    """Best-looking encoding of `im` that fits `target`, or the smallest one we tried."""
    if ext in images.LOSSY:
        lo, hi, fit = min(MIN_QUALITY, max_quality), max_quality, None
        while lo <= hi:
            q = (lo + hi) // 2
            data = images.encode(im, ext, q, meta)
            if len(data) <= target:
                fit, lo = data, q + 1
            else:
                hi = q - 1
        return fit or images.encode(im, ext, min(MIN_QUALITY, max_quality), meta)

    data = images.encode(im, ext, meta=meta)
    if len(data) <= target or ext not in ("png", "gif", "tiff", "bmp"):
        return data
    # Lossless formats: a 256-colour palette usually halves the size with little visible change.
    # Only PNG and GIF keep transparency through a palette, so the others get RGB only.
    if im.mode == "RGB" or (im.mode == "RGBA" and ext in ("png", "gif")):
        quantized = im.quantize(256, method=Image.Quantize.FASTOCTREE)
        return min(data, images.encode(quantized, ext, meta=meta), key=len)
    return data


def _is_animated(path: Path) -> bool:
    with Image.open(path) as im:
        return getattr(im, "n_frames", 1) > 1


def _shrink_animated_gif(path: Path, target: int) -> bytes:
    """Keep the animation: drop frames (merging their display time) and scale every frame down."""
    with Image.open(path) as im:
        loop = im.info.get("loop", 0)
        frames, durations = [], []
        for frame in ImageSequence.Iterator(im):
            durations.append(frame.info.get("duration", 100))
            frames.append(frame.convert("RGBA"))

    best: bytes | None = None
    scale, step = 1.0, 1
    for _ in range(MAX_RESIZE_STEPS):
        tools.check_cancelled()
        w, h = round(frames[0].width * scale), round(frames[0].height * scale)
        if min(w, h) < MIN_SIDE:
            break
        picked = [f if scale == 1.0 else f.resize((w, h), Image.Resampling.LANCZOS) for f in frames[::step]]
        shown_for = [sum(durations[i:i + step]) for i in range(0, len(frames), step)]
        buf = io.BytesIO()
        picked[0].save(buf, "GIF", save_all=True, append_images=picked[1:], duration=shown_for,
                       loop=loop, disposal=2, optimize=True)
        data = buf.getvalue()
        if best is None or len(data) < len(best):
            best = data
        if len(data) <= target:
            break
        ratio = target / len(data)
        # Far over the limit with plenty of frames: halve the frame rate as well as shrinking.
        if ratio < 0.5 and step < 4 and len(frames) // (step * 2) >= 10:
            step *= 2
        scale *= max(0.3, min(0.9, ratio ** 0.5 * 0.95))
    return best if best is not None else path.read_bytes()


# --- PDF ----------------------------------------------------------------------------


def _shrink_pdf(path: Path, target: int) -> bytes | None:
    best: bytes | None = None
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        out = Path(tmp) / "out.pdf"
        for preset, dpi in PDF_LEVELS:
            cmd = [
                tools.ghostscript(), "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dNOPAUSE", "-dBATCH",
                "-dQUIET", "-dSAFER", f"-dPDFSETTINGS={preset}",
                "-dDownsampleColorImages=true", "-dDownsampleGrayImages=true", "-dDownsampleMonoImages=true",
                f"-dColorImageResolution={dpi}", f"-dGrayImageResolution={dpi}",
                f"-dMonoImageResolution={dpi * 2}",
                f"-sOutputFile={out}", str(path),
            ]
            try:
                code, _ = tools.run(cmd, timeout=300)
            except TimeoutError:
                continue
            if code != 0:
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


# --- audio and video ----------------------------------------------------------------

# Leave room for container overhead, which grows with length.
MEDIA_HEADROOM = 0.93
MEDIA_ATTEMPTS = 3
MIN_AUDIO_KBPS = 24
MIN_VIDEO_KBPS = 40
# Lower the resolution as the bitrate drops, or the picture turns to blocks: (kbps below, max height).
VIDEO_HEIGHTS = [(400, 360), (1000, 480), (2500, 720)]


def _shrink_media(path: Path, ext: str, target: int) -> str:
    """Re-encode at a bitrate worked out from the length; retry a little lower if the result
    still comes out too big. Returns a note for the user (empty when there's nothing to say)."""
    seconds = media.duration(path)
    if not seconds:
        return "Couldn't read how long this file is, so it wasn't compressed."
    kbps = target * 8 / 1000 / seconds * MEDIA_HEADROOM
    best: Path | None = None
    with tempfile.TemporaryDirectory(dir=path.parent, ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        for attempt in range(MEDIA_ATTEMPTS):
            out = work / f"try{attempt}.{ext}"
            if ext in media.VIDEO:
                if not _encode_video(path, out, ext, kbps, work):
                    return "This video is too long to fit under that limit at any watchable quality."
            else:
                _encode_audio(path, out, ext, max(kbps, MIN_AUDIO_KBPS))
            if best is None or out.stat().st_size < best.stat().st_size:
                best = out
            size = out.stat().st_size
            if size <= target:
                break
            kbps *= target / size * 0.95
        if best is not None and best.stat().st_size < path.stat().st_size:
            best.replace(path)
    return ""


def _encode_audio(src: Path, dst: Path, ext: str, kbps: float) -> None:
    args = ["-i", str(src), "-vn", *media.AUDIO_CODECS[ext], "-b:a", f"{int(kbps)}k"]
    if kbps < 48:
        args += ["-ac", "1"]  # at very low bitrates, mono sounds far better than squeezed stereo
    if kbps < 32 and ext != "opus":
        args += ["-ar", "22050"]
    media.ffmpeg([*args, str(dst)])


def _encode_video(src: Path, dst: Path, ext: str, kbps: float, work: Path) -> bool:
    audio_kbps = 64 if kbps > 400 else 32
    video_kbps = kbps - audio_kbps
    if video_kbps < MIN_VIDEO_KBPS:
        return False
    height = next((h for limit, h in VIDEO_HEIGHTS if video_kbps < limit), None)
    vcodec, acodec = media.VIDEO_CODECS[ext]
    scale = f"scale=-2:'min(trunc(ih/2)*2,{height})'" if height else media.EVEN_SIZE
    common = ["-i", str(src), "-c:v", vcodec, "-b:v", f"{int(video_kbps)}k", "-vf", scale,
              "-passlogfile", str(work / "pass")]
    if vcodec == "libx264":
        common += ["-preset", "medium", "-pix_fmt", "yuv420p"]
    # Pass 1 only studies the video; pass 2 spends the bitrate where the picture needs it.
    media.ffmpeg([*common, "-pass", "1", "-an", "-f", "null", "-"], cwd=work)
    media.ffmpeg([*common, "-pass", "2", "-c:a", acodec, "-b:a", f"{audio_kbps}k", str(dst)], cwd=work)
    return True


# --- zips of several results --------------------------------------------------------


def _shrink_zip_members(path: Path, target: int) -> Shrunk:
    # Work next to the zip so the final replace() stays on the same disk.
    with tempfile.TemporaryDirectory(dir=path.parent, ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        missed = 0
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(work / "out.zip", "w", zipfile.ZIP_DEFLATED) as dst:
            members = [i for i in src.infolist() if not i.is_dir()]
            for i, info in enumerate(members):
                tools.check_cancelled()
                # Extract under a numbered name: never trust paths stored inside a zip.
                member = work / f"{i}{Path(info.filename).suffix}"
                member.write_bytes(src.read(info))
                if not shrink(member, target, zip_fallback=False).met:
                    missed += 1
                dst.write(member, info.filename)
        (work / "out.zip").replace(path)

    note = f"The {human(target)} limit was applied to each file in the zip."
    if missed:
        note += f" {missed} of {len(members)} files are still above it."
    return Shrunk(path, missed == 0, note)


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
