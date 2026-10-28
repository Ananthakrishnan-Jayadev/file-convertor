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


def encode(im: Image.Image, fmt: str, quality: int | None = None) -> bytes:
    kwargs: dict = {}
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
def convert_image(src: Path, out_dir: Path, fmt: str) -> Path:
    im = prepare(load(src), fmt)
    dst = out_dir / f"{src.stem}.{fmt}"
    dst.write_bytes(encode(im, fmt))
    return dst
