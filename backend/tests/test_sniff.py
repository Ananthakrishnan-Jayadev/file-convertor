import pytest

from app.sniff import family, mismatch


@pytest.mark.parametrize("head, expected", [
    (b"%PDF-1.7\n", "pdf"),
    (b"\x89PNG\r\n\x1a\n....", "image"),
    (b"\xff\xd8\xff\xe0", "image"),
    (b"GIF89a", "image"),
    (b"BM\x36\x00\x0c\x00\x00\x00\x00\x00", "image"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image"),
    (b"\x00\x00\x00\x18ftypheic", "image"),
    (b"\x00\x00\x00\x1cftypavif", "image"),
    (b"\x00\x00\x00\x18ftypisom", "media"),
    (b"\x00\x00\x00\x14ftypqt  ", "media"),
    (b"RIFF\x00\x00\x00\x00WAVEfmt ", "media"),
    (b"ID3\x04\x00", "media"),
    (b"\xff\xfb\x90\x00", "media"),
    (b"fLaC", "media"),
    (b"OggS", "media"),
    (b"\x1a\x45\xdf\xa3", "media"),
    (b"PK\x03\x04", "zip"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"),
    (b"{\\rtf1\\ansi", "rtf"),
    (b"name,age\nAsha,31\n", "text"),
    (b"BMW,Audi\n1,2\n", "text"),  # starts with "BM" but isn't a bitmap
    (b"ID3 tags explained\n", "text"),
    (b"\xff\xfen\x00a\x00m\x00e\x00", "text"),  # UTF-16 with BOM
    (b"\x00\x01\x02\x03binary", None),
])
def test_family(head, expected):
    assert family(head) == expected


@pytest.mark.parametrize("ext, head", [
    ("png", b"\xff\xd8\xff\xe0"),  # a JPEG named .png: Pillow copes
    ("doc", b"{\\rtf1"),  # an RTF named .doc: LibreOffice copes
    ("mov", b"\x00\x00\x00\x18ftypisom"),
    ("csv", b"a,b\n1,2\n"),
    ("png", b"\x00\x01\x02\x03"),  # unknown contents are let through
    ("exe", b"MZ"),  # unknown extensions are someone else's problem
])
def test_allowed(ext, head):
    assert mismatch(ext, head) is None


@pytest.mark.parametrize("ext, head, word", [
    ("pdf", b"\xff\xd8\xff\xe0", "an image"),
    ("docx", b"%PDF-1.4", "a PDF"),
    ("jpg", b"hello there", "a text file"),
    ("mp4", b"%PDF-1.4", "a PDF"),
    ("csv", b"PK\x03\x04", "zip"),
])
def test_rejected(ext, head, word):
    message = mismatch(ext, head)
    assert message and f".{ext}" in message and word in message
