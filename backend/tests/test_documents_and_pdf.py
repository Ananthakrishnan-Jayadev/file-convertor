import zipfile

import pymupdf
import pytest
from PIL import Image

from app.converters.documents import convert_markdown, convert_writer
from app.converters.pdf import convert_pdf

from .conftest import needs_soffice


def test_pdf_pages_to_png_zip(pdf_two_pages, out_dir):
    dst = convert_pdf(pdf_two_pages, out_dir, "png")
    with zipfile.ZipFile(dst) as zf:
        assert zf.namelist() == ["report-page1.png", "report-page2.png"]


@pytest.mark.parametrize("fmt", ["jpg", "webp"])
def test_single_page_pdf_to_one_image(pdf_with_photo, out_dir, fmt):
    dst = convert_pdf(pdf_with_photo, out_dir, fmt)
    assert dst.suffix == f".{fmt}"
    with Image.open(dst) as im:
        assert im.width > 500


def test_pdf_to_text(pdf_two_pages, out_dir):
    text = convert_pdf(pdf_two_pages, out_dir, "txt").read_text()
    assert "Hello page 1" in text and "Hello page 2" in text


@pytest.mark.slow
def test_pdf_to_docx(pdf_two_pages, out_dir):
    dst = convert_pdf(pdf_two_pages, out_dir, "docx")
    with zipfile.ZipFile(dst) as zf:
        assert "Hello page 1" in zf.read("word/document.xml").decode()


def test_markdown_to_html_needs_no_libreoffice(markdown_file, out_dir):
    html = convert_markdown(markdown_file, out_dir, "html").read_text()
    assert "<h1>Title</h1>" in html and "<table>" in html


@needs_soffice
@pytest.mark.slow
def test_markdown_to_docx_to_pdf(markdown_file, out_dir, tmp_path):
    docx = convert_markdown(markdown_file, out_dir, "docx")
    assert zipfile.is_zipfile(docx)
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    pdf = convert_writer(docx, pdf_dir, "pdf")
    with pymupdf.open(pdf) as doc:
        assert "Title" in doc[0].get_text()


@needs_soffice
@pytest.mark.slow
@pytest.mark.parametrize("fmt", ["odt", "rtf", "txt", "doc", "md"])
def test_docx_to_other_document_formats(markdown_file, out_dir, tmp_path, fmt):
    docx = convert_markdown(markdown_file, out_dir, "docx")
    dst_dir = tmp_path / fmt
    dst_dir.mkdir()
    dst = convert_writer(docx, dst_dir, fmt)
    assert dst.suffix == f".{fmt}" and dst.stat().st_size > 0
    if fmt in ("txt", "md"):
        assert "Title" in dst.read_text(encoding="utf-8-sig")


@needs_soffice
@pytest.mark.slow
def test_csv_to_pdf_via_libreoffice(csv_file, out_dir):
    from app.converters.documents import convert_sheet_pdf

    with pymupdf.open(convert_sheet_pdf(csv_file, out_dir, "pdf")) as doc:
        assert "Asha" in doc[0].get_text()
