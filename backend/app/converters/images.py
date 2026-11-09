from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

from ..registry import register

pillow_heif.register_heif_opener()

IMAGE_IN = {"png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "heic", "avif"}
IMAGE_OUT = {"png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "heic", "avif", "pdf"}
LOSSY = {"jpg", "webp", "avif", "heic"}

_PIL_FORMAT = {
    "jpg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP", "gif": "GIF",
    "tiff": "TIFF", "ico": "ICO", "avif": "AVIF", "heic": "HEIF", "pdf": "PDF",
}
_NO_ALPHA = {"jpg", "bmp", "pdf"}
# Formats that can carry a colour profile and EXIF data.
_META_FORMATS = {"jpg", "png", "webp", "tiff", "avif", "heic"}
_ROTATE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}


@dataclass(frozen=True)
class ImageOptions:
    """Optional edits applied while converting an image."""

    width: int | None = None  # fit within width x height, keeping the aspect ratio; never enlarges
    height: int | None = None
    scale: int | None = None  # percent of the original size, 1-100
    rotate: int = 0  # degrees clockwise: 0, 90, 180 or 270
    quality: int | None = None  # 1-100, for JPG/WEBP/AVIF/HEIC; None means automatic
    keep_metadata: bool = False  # keep EXIF: date, camera and GPS location

    def is_default(self) -> bool:
        return self == ImageOptions()


def load(src: Path) -> Image.Image:
    im = Image.open(src)
    im.load()
    # Phone photos store rotation in EXIF; bake it in so the output isn't sideways.
    return ImageOps.exif_transpose(im)


def has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)


def prepare(im: Image.Image, fmt: str) -> Image.Image:
    alpha = has_alpha(im)
    if fmt in _NO_ALPHA:
        if alpha:
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            return bg
        return im if im.mode in ("RGB", "L") else im.convert("RGB")
    if im.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        return im.convert("RGBA" if alpha else "RGB")
    return im


def metadata(im: Image.Image, keep_exif: bool) -> dict:
    """What to carry over to the output. The colour profile always comes along, since dropping
    it shifts colours; EXIF only on request, since it can include where a photo was taken."""
    meta = {}
    if icc := im.info.get("icc_profile"):
        meta["icc_profile"] = icc
    if keep_exif and len(exif := im.getexif()):
        meta["exif"] = exif.tobytes()
    return meta


def transform(im: Image.Image, opts: ImageOptions) -> Image.Image:
    # Rotate first, so width and height refer to the picture as it will be seen.
    if opts.rotate in _ROTATE:
        im = im.transpose(_ROTATE[opts.rotate])
    if opts.scale and opts.scale < 100:
        ratio = opts.scale / 100
    elif opts.width or opts.height:
        ratio = min(opts.width / im.width if opts.width else 1, opts.height / im.height if opts.height else 1, 1)
    else:
        return im
    if ratio >= 1:
        return im
    size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
    return im.resize(size, Image.Resampling.LANCZOS)


def encode(im: Image.Image, fmt: str, quality: int | None = None, meta: dict | None = None) -> bytes:
    kwargs: dict = dict(meta) if meta and fmt in _META_FORMATS else {}
    if fmt in LOSSY:
        kwargs["quality"] = quality or 90
    if fmt == "jpg":
        kwargs.update(optimize=True, progressive=True)
    elif fmt == "png":
        kwargs["optimize"] = True
    elif fmt == "webp":
        kwargs["method"] = 6
    elif fmt == "tiff":
        kwargs["compression"] = "tiff_adobe_deflate"
    elif fmt == "pdf":
        kwargs["resolution"] = 150
    buf = BytesIO()
    im.save(buf, _PIL_FORMAT[fmt], **kwargs)
    return buf.getvalue()


@register("image", IMAGE_IN, IMAGE_OUT)
def convert_image(src: Path, out_dir: Path, fmt: str, options: ImageOptions | None = None) -> Path:
    opts = options or ImageOptions()
    im = load(src)
    meta = metadata(im, opts.keep_metadata)
    im = prepare(transform(im, opts), fmt)
    dst = out_dir / f"{src.stem}.{fmt}"
    dst.write_bytes(encode(im, fmt, opts.quality, meta))
    return dst
