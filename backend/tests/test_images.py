import pytest
from PIL import Image, ImageCms

from app.converters.images import IMAGE_OUT, ImageOptions, convert_image


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


# --- image options ----------------------------------------------------------------------


def size_of(path):
    with Image.open(path) as im:
        return im.size


def test_scale_option(big_jpg, out_dir):
    assert size_of(convert_image(big_jpg, out_dir, "png", ImageOptions(scale=50))) == (800, 600)


def test_fit_keeps_shape(big_jpg, out_dir):
    assert size_of(convert_image(big_jpg, out_dir, "png", ImageOptions(width=400, height=400))) == (400, 300)


def test_fit_with_only_height(big_jpg, out_dir):
    assert size_of(convert_image(big_jpg, out_dir, "png", ImageOptions(height=300))) == (400, 300)


def test_fit_never_enlarges(png_alpha, out_dir):
    assert size_of(convert_image(png_alpha, out_dir, "png", ImageOptions(width=5000))) == (200, 120)


@pytest.mark.parametrize("deg, expected", [(90, (120, 200)), (180, (200, 120)), (270, (120, 200))])
def test_rotate_option(png_alpha, out_dir, deg, expected):
    assert size_of(convert_image(png_alpha, out_dir, "png", ImageOptions(rotate=deg))) == expected


def test_rotate_is_clockwise(tmp_path, out_dir):
    src = tmp_path / "marker.png"
    im = Image.new("RGB", (40, 20), "white")
    im.putpixel((0, 0), (255, 0, 0))  # red dot top-left
    im.save(src)
    with Image.open(convert_image(src, out_dir, "png", ImageOptions(rotate=90))) as out:
        assert out.getpixel((19, 0)) == (255, 0, 0)  # turned clockwise: now top-right


def test_rotate_then_fit(big_jpg, out_dir):
    # Width and height refer to the picture after rotating.
    opts = ImageOptions(rotate=90, width=300)
    assert size_of(convert_image(big_jpg, out_dir, "png", opts)) == (300, 400)


def test_quality_option(big_jpg, tmp_path):
    low_dir, high_dir = tmp_path / "low", tmp_path / "high"
    low_dir.mkdir()
    high_dir.mkdir()
    low = convert_image(big_jpg, low_dir, "jpg", ImageOptions(quality=20))
    high = convert_image(big_jpg, high_dir, "jpg", ImageOptions(quality=95))
    assert low.stat().st_size < high.stat().st_size / 2


@pytest.fixture
def photo_with_details(tmp_path):
    src = tmp_path / "holiday.jpg"
    exif = Image.Exif()
    exif[0x0132] = "2024:07:01 12:00:00"  # DateTime
    exif[0x010F] = "PhoneMaker"  # camera make
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (64, 48), "teal").save(src, exif=exif, icc_profile=icc)
    return src, icc


def test_photo_details_removed_by_default(photo_with_details, out_dir):
    src, _ = photo_with_details
    with Image.open(convert_image(src, out_dir, "jpg")) as im:
        assert 0x0132 not in im.getexif() and 0x010F not in im.getexif()


def test_photo_details_kept_on_request(photo_with_details, out_dir):
    src, _ = photo_with_details
    with Image.open(convert_image(src, out_dir, "webp", ImageOptions(keep_metadata=True))) as im:
        assert im.getexif()[0x010F] == "PhoneMaker"


@pytest.mark.parametrize("fmt", ["jpg", "png", "webp", "tiff"])
def test_colour_profile_always_kept(photo_with_details, out_dir, fmt):
    src, icc = photo_with_details
    with Image.open(convert_image(src, out_dir, fmt)) as im:
        assert im.info.get("icc_profile") == icc
