"""Check that a file's contents match its extension, using the first few bytes.

Only clear contradictions are rejected, such as a ".pdf" that is really a JPEG. Mix-ups inside
one family are let through because the converter handles them anyway: Pillow opens a JPEG named
".png", LibreOffice opens an RTF named ".doc", and FFmpeg reads any audio or video container.
Unknown contents are let through too, rather than blocking a file we simply don't recognise.
"""

HEAD_BYTES = 8192

# What each family looks like, for error messages.
DESCRIPTIONS = {
    "image": "an image",
    "pdf": "a PDF",
    "zip": "a zip archive or a modern Office file",
    "ole": "an older Office file (.doc, .xls or .ppt)",
    "rtf": "an RTF document",
    "media": "an audio or video file",
    "text": "a text file",
}

# Which content families each extension may contain.
_EXPECTED = {
    **dict.fromkeys(["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "heic", "avif"], {"image"}),
    "pdf": {"pdf"},
    **dict.fromkeys(["docx", "xlsx", "pptx", "odt", "ods", "odp", "epub"], {"zip"}),
    # Old Office formats are often really RTF, HTML or CSV saved with the old extension.
    **dict.fromkeys(["doc", "xls", "ppt"], {"ole", "rtf", "text"}),
    "rtf": {"rtf", "text"},
    **dict.fromkeys(["csv", "tsv", "txt", "md", "html", "json", "yaml", "xml"], {"text", "rtf"}),
    **dict.fromkeys(["mp3", "wav", "aac", "m4a", "ogg", "flac", "opus",
                     "mp4", "mov", "webm", "mkv", "avi"], {"media"}),
}

# ISO base media brands (bytes 8-12 of an "ftyp" box) used by HEIC/AVIF images.
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1", b"avif", b"avis"}


def family(head: bytes) -> str | None:
    """Content family of a file from its first bytes, or None when we can't tell."""
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a",
                        b"II*\x00", b"MM\x00*", b"\x00\x00\x01\x00", b"\x00\x00\x02\x00")):
        return "image"
    # "BM" alone would match a CSV starting with "BMW,"; BMP headers have 4 reserved zero bytes.
    if head.startswith(b"BM") and head[6:10] == b"\x00\x00\x00\x00":
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    if head[4:8] == b"ftyp":
        return "image" if head[8:12] in _HEIF_BRANDS else "media"
    if head[:4] == b"RIFF" and head[8:12] in (b"WAVE", b"AVI "):
        return "media"
    if head.startswith((b"fLaC", b"OggS", b"\x1a\x45\xdf\xa3")) or head[4:8] in (b"moov", b"mdat", b"wide"):
        return "media"
    if head[:3] == b"ID3" and head[3:4] < b"\x10":  # MP3 tag; the version byte rules out plain text
        return "media"
    # UTF-16 text starts with FF FE / FE FF, which would also pass the MP3 check below.
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "text"
    if len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0:  # MP3 / AAC frame sync
        return "media"
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole"
    if head.startswith(b"{\\rtf"):
        return "rtf"
    if head.startswith(b"\xef\xbb\xbf") or (head and b"\x00" not in head):
        return "text"
    return None


def mismatch(ext: str, head: bytes) -> str | None:
    """An error message when the contents clearly aren't what the extension says, else None."""
    expected = _EXPECTED.get(ext)
    found = family(head)
    if expected is None or found is None or found in expected:
        return None
    return f"This file is named .{ext} but it looks like {DESCRIPTIONS[found]}. Check that you picked the right file."
