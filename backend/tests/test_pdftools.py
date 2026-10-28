import zipfile

import pymupdf
import pytest
from PIL import Image

from app import pdftools


def make_pdf(path, pages: int, prefix: str = "Page"):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"{prefix} {i + 1}")
    doc.save(path)
    doc.close()
    return path


def page_texts(path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text().strip() for page in doc]


# --- parse_ranges ---------------------------------------------------------------------


@pytest.mark.parametrize("spec, expected", [
    ("1-3, 5, 8-", [(1, 3), (5, 5), (8, 10)]),
    ("-2", [(1, 2)]),
    ("4 - 6", [(4, 6)]),
    ("10", [(10, 10)]),
    ("1-10", [(1, 10)]),
    (" 2 ,, 3 ", [(2, 2), (3, 3)]),
])
def test_parse_ranges(spec, expected):
    assert pdftools.parse_ranges(spec, 10) == expected


@pytest.mark.parametrize("spec, message", [
    ("", "at least one"),
    ("abc", "isn't a page or range"),
    ("1-2-3", "isn't a page or range"),
    ("0", "outside this PDF"),
    ("3-11", "outside this PDF, which has 10 pages"),
    ("5-2", "backwards"),
])
def test_parse_ranges_errors(spec, message):
    with pytest.raises(ValueError, match=message):
        pdftools.parse_ranges(spec, 10)


def test_single_page_error_uses_singular():
    with pytest.raises(ValueError, match="has 1 page\\."):
        pdftools.parse_ranges("2", 1)


# --- combine ----------------------------------------------------------------------------


def test_combine_keeps_order_of_pdfs_and_images(tmp_path, png_alpha, big_jpg):
    a = make_pdf(tmp_path / "a.pdf", 2, "A")
    b = make_pdf(tmp_path / "b.pdf", 1, "B")
    dst = pdftools.combine([a, big_jpg, b, png_alpha], tmp_path / "out.pdf")

    with pymupdf.open(dst) as doc:
        assert doc.page_count == 5
        assert doc[0].get_text().strip() == "A 1"
        assert doc[1].get_text().strip() == "A 2"
        assert len(doc[2].get_images()) == 1  # the photo
        assert doc[3].get_text().strip() == "B 1"
        assert len(doc[4].get_images()) == 1  # the logo


def test_image_page_matches_image_shape(tmp_path, big_jpg):
    dst = pdftools.combine([big_jpg], tmp_path / "out.pdf")
    with pymupdf.open(dst) as doc:
        rect = doc[0].rect
        assert rect.width / rect.height == pytest.approx(1600 / 1200, rel=0.01)


def test_rotated_phone_photo_is_upright(tmp_path):
    src = tmp_path / "phone.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise
    Image.new("RGB", (300, 100), "white").save(src, exif=exif)
    dst = pdftools.combine([src], tmp_path / "out.pdf")
    with pymupdf.open(dst) as doc:
        assert doc[0].rect.height > doc[0].rect.width


# --- split ------------------------------------------------------------------------------


def test_split_every_page(tmp_path, out_dir):
    src = make_pdf(tmp_path / "book.pdf", 3)
    dst = pdftools.split(src, out_dir, None)
    assert dst.name == "book-split.zip"
    with zipfile.ZipFile(dst) as zf:
        assert zf.namelist() == ["book-page1.pdf", "book-page2.pdf", "book-page3.pdf"]
        part = tmp_path / "p2.pdf"
        part.write_bytes(zf.read("book-page2.pdf"))
    assert page_texts(part) == ["Page 2"]


def test_split_ranges(tmp_path, out_dir):
    src = make_pdf(tmp_path / "book.pdf", 6)
    dst = pdftools.split(src, out_dir, pdftools.parse_ranges("1-2, 4, 5-", 6))
    with zipfile.ZipFile(dst) as zf:
        assert zf.namelist() == ["book-pages1-2.pdf", "book-page4.pdf", "book-pages5-6.pdf"]
        last = tmp_path / "last.pdf"
        last.write_bytes(zf.read("book-pages5-6.pdf"))
    assert page_texts(last) == ["Page 5", "Page 6"]


def test_single_range_gives_a_pdf_not_a_zip(tmp_path, out_dir):
    src = make_pdf(tmp_path / "book.pdf", 5)
    dst = pdftools.split(src, out_dir, [(2, 3)])
    assert dst.name == "book-pages2-3.pdf"
    assert page_texts(dst) == ["Page 2", "Page 3"]
