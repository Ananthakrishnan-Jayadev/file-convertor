import pytest
from PIL import Image

from app.converters.images import IMAGE_OUT, convert_image


@pytest.mark.parametrize("fmt", sorted(IMAGE_OUT - {"pdf"}))
def test_png_converts_to_every_image_format(png_alpha, out_dir, fmt):
    dst = convert_image(png_alpha, out_dir, fmt)
    assert dst.suffix == f".{fmt}"
    with Image.open(dst) as im:
        im.load()
        assert im.size[0] > 0


def test_png_to_pdf(png_alpha, out_dir):
    dst = convert_image(png_alpha, out_dir, "pdf")
    assert dst.read_bytes().startswith(b"%PDF")


def test_transparency_becomes_white_in_jpg(png_alpha, out_dir):
    dst = convert_image(png_alpha, out_dir, "jpg")
    with Image.open(dst) as im:
        assert im.mode == "RGB"
        r, g, b = im.getpixel((5, 5))  # a transparent corner in the source
        assert min(r, g, b) > 240


def test_transparency_kept_in_webp(png_alpha, out_dir):
    dst = convert_image(png_alpha, out_dir, "webp")
    with Image.open(dst) as im:
        assert im.mode == "RGBA"
        assert im.getpixel((5, 5))[3] == 0


def test_exif_rotation_is_applied(tmp_path, out_dir):
    src = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90° clockwise
    Image.new("RGB", (300, 100), "white").save(src, exif=exif)
    dst = convert_image(src, out_dir, "png")
    with Image.open(dst) as im:
        assert im.size == (100, 300)


def test_heic_roundtrip(png_alpha, out_dir, tmp_path):
    heic = convert_image(png_alpha, out_dir, "heic")
    back_dir = tmp_path / "back"
    back_dir.mkdir()
    png = convert_image(heic, back_dir, "png")
    with Image.open(png) as im:
        assert im.size == (200, 120)


def test_not_an_image_raises(tmp_path, out_dir):
    src = tmp_path / "fake.png"
    src.write_text("definitely not a png")
    with pytest.raises(Exception):
        convert_image(src, out_dir, "jpg")
