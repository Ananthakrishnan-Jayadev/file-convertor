import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import pymupdf
import pytest
from PIL import Image

# Must be set before the app is imported, since jobs.py reads it at import time.
os.environ.setdefault("FC_DATA_DIR", tempfile.mkdtemp(prefix="fc-test-"))
os.environ.setdefault("FC_JOB_TTL", "3600")

HAS_SOFFICE = shutil.which(os.environ.get("SOFFICE_BIN", "soffice")) is not None
HAS_GS = shutil.which(os.environ.get("GS_BIN", "gs")) is not None
needs_soffice = pytest.mark.skipif(not HAS_SOFFICE, reason="LibreOffice (soffice) not installed")
needs_gs = pytest.mark.skipif(not HAS_GS, reason="Ghostscript (gs) not installed")


def photo(size=(1600, 1200)) -> Image.Image:
    """A gradient with noise: compresses like a real photo, unlike a flat colour."""
    w, h = size
    gradient = Image.linear_gradient("L").resize(size)
    noise = Image.effect_noise(size, 40)
    return Image.merge("RGB", (gradient, noise, gradient.rotate(90).resize(size)))


@pytest.fixture
def out_dir(tmp_path) -> Path:
    d = tmp_path / "out"
    d.mkdir()
    return d


@pytest.fixture
def png_alpha(tmp_path) -> Path:
    im = Image.new("RGBA", (200, 120), (255, 0, 0, 0))
    im.paste((0, 128, 255, 255), (50, 30, 150, 90))
    path = tmp_path / "logo.png"
    im.save(path)
    return path


@pytest.fixture
def big_jpg(tmp_path) -> Path:
    path = tmp_path / "photo.jpg"
    photo().save(path, quality=95)
    return path


@pytest.fixture
def big_png(tmp_path) -> Path:
    path = tmp_path / "screenshot.png"
    photo((1200, 900)).save(path)
    return path


@pytest.fixture
def csv_file(tmp_path) -> Path:
    path = tmp_path / "people.csv"
    path.write_text("name,age,city\nAsha,31,Toronto\nBen,45,Oshawa\nChloé,28,Montréal\n", encoding="utf-8")
    return path


@pytest.fixture
def xlsx_two_sheets(tmp_path) -> Path:
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_excel(w, sheet_name="First", index=False)
        pd.DataFrame({"c": [3.5]}).to_excel(w, sheet_name="Second", index=False)
    return path


@pytest.fixture
def pdf_two_pages(tmp_path) -> Path:
    path = tmp_path / "report.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Hello page {i + 1}", fontsize=18)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def pdf_with_photo(tmp_path) -> Path:
    img = tmp_path / "embed.png"
    photo((2400, 1800)).save(img)
    path = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=str(img))
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def markdown_file(tmp_path) -> Path:
    path = tmp_path / "notes.md"
    path.write_text("# Title\n\nSome **bold** text.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_docx_with_photo(tmp_path) -> Path:
    """Enough of a DOCX for the size controller: a zip with a big picture in word/media."""
    path = tmp_path / "essay.docx"
    pic = tmp_path / "image1.jpg"
    photo((2400, 1800)).save(pic, quality=95)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
        zf.write(pic, "word/media/image1.jpg")
    return path
