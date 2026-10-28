import os
import zipfile

import pytest
from PIL import Image

from app.compress import human, shrink
from app.converters.images import convert_image

from .conftest import needs_gs

KB = 1024


def test_already_small_file_is_untouched(csv_file):
    before = csv_file.read_bytes()
    result = shrink(csv_file, 500 * KB)
    assert result.met and result.path == csv_file and csv_file.read_bytes() == before


def test_jpg_under_limit_keeps_dimensions_when_quality_is_enough(big_jpg):
    target = big_jpg.stat().st_size // 2
    result = shrink(big_jpg, target)
    assert result.met and result.path.stat().st_size <= target
    with Image.open(result.path) as im:
        assert im.size == (1600, 1200)


def test_jpg_tiny_limit_downscales(big_jpg):
    result = shrink(big_jpg, 30 * KB)
    assert result.met and result.path.stat().st_size <= 30 * KB
    with Image.open(result.path) as im:
        assert im.width < 1600


@pytest.mark.parametrize("fmt", ["webp", "avif"])
def test_modern_formats_hit_target(big_jpg, out_dir, fmt):
    converted = convert_image(big_jpg, out_dir, fmt)
    result = shrink(converted, 100 * KB)
    assert result.met and result.path.stat().st_size <= 100 * KB


def test_png_shrinks_and_stays_png(big_png):
    target = 300 * KB
    assert big_png.stat().st_size > target
    result = shrink(big_png, target)
    assert result.met and result.path.suffix == ".png"
    with Image.open(result.path) as im:
        im.load()


def test_png_keeps_transparency(png_alpha, tmp_path):
    src = tmp_path / "big-alpha.png"
    Image.open(png_alpha).resize((2000, 1200)).save(src)
    result = shrink(src, max(10 * KB, src.stat().st_size // 3))
    with Image.open(result.path) as im:
        assert im.convert("RGBA").getpixel((5, 5))[3] == 0


def test_docx_pictures_are_recompressed(fake_docx_with_photo):
    before = fake_docx_with_photo.stat().st_size
    result = shrink(fake_docx_with_photo, before // 4)
    assert result.met and result.path.stat().st_size <= before // 4
    with zipfile.ZipFile(result.path) as zf:
        assert set(zf.namelist()) == {"[Content_Types].xml", "word/document.xml", "word/media/image1.jpg"}
        with Image.open(zf.open("word/media/image1.jpg")) as im:
            im.load()


def test_odf_mimetype_stays_first_and_stored(tmp_path, big_jpg):
    path = tmp_path / "doc.odt"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text", compress_type=zipfile.ZIP_STORED)
        zf.write(big_jpg, "Pictures/photo.jpg")
    shrink(path, path.stat().st_size // 3)
    with zipfile.ZipFile(path) as zf:
        first = zf.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED


@needs_gs
def test_pdf_is_compressed_with_ghostscript(pdf_with_photo):
    before = pdf_with_photo.stat().st_size
    result = shrink(pdf_with_photo, before // 3)
    assert result.path.read_bytes().startswith(b"%PDF")
    assert result.path.stat().st_size < before


def test_text_file_falls_back_to_zip(tmp_path):
    src = tmp_path / "log.txt"
    src.write_text("the same line again\n" * 50_000)
    result = shrink(src, 50 * KB)
    assert result.met and result.path.name == "log.txt.zip"
    assert not src.exists()
    assert "zip" in result.note
    with zipfile.ZipFile(result.path) as zf:
        assert zf.namelist() == ["log.txt"]


def test_impossible_target_reports_smallest_size(tmp_path):
    src = tmp_path / "noise.csv"
    src.write_bytes(os.urandom(100 * KB))  # random bytes don't compress at all
    result = shrink(src, 10 * KB)
    assert not result.met
    assert result.path == src  # zipping didn't help, so the original is kept
    assert "smallest" in result.note


@pytest.mark.parametrize("n, text", [(500, "500 B"), (2048, "2 KB"), (5 * 1024 * 1024, "5.0 MB")])
def test_human(n, text):
    assert human(n) == text


def test_zip_limit_applies_to_each_file(tmp_path, big_jpg):
    path = tmp_path / "pages.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(big_jpg, "one.jpg")
        zf.write(big_jpg, "sub/two.jpg")
    result = shrink(path, 80 * KB)
    assert result.met and result.path == path
    assert "each file" in result.note
    with zipfile.ZipFile(path) as zf:
        assert zf.namelist() == ["one.jpg", "sub/two.jpg"]
        assert all(i.file_size <= 80 * KB for i in zf.infolist())


def test_zip_reports_files_still_over_limit(tmp_path):
    path = tmp_path / "data.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("noise.csv", os.urandom(60 * KB))
        zf.writestr("small.csv", b"a,b\n1,2\n")
    result = shrink(path, 20 * KB)
    assert not result.met
    assert "1 of 2 files" in result.note
    with zipfile.ZipFile(path) as zf:
        assert zf.namelist() == ["noise.csv", "small.csv"]  # no nested zips
