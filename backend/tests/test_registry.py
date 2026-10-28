import pytest

from app import converters  # noqa: F401
from app.registry import find, format_map, normalize


@pytest.mark.parametrize("raw, expected", [
    (".JPEG", "jpg"), ("jpe", "jpg"), (".tif", "tiff"), ("HEIF", "heic"), (".yml", "yaml"),
    (".htm", "html"), ("markdown", "md"), (".png", "png"),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_format_map_covers_main_categories():
    fm = format_map()
    assert {"jpg", "png", "webp", "avif"} <= set(fm["png"]["outputs"])
    assert {"pdf", "docx", "odt", "rtf", "txt", "md"} <= set(fm["docx"]["outputs"])
    assert {"xlsx", "json", "pdf"} <= set(fm["csv"]["outputs"])
    assert {"csv", "ods", "json"} <= set(fm["xlsx"]["outputs"])
    assert {"docx", "png", "txt"} <= set(fm["pdf"]["outputs"])
    assert {"yaml", "xml", "csv"} <= set(fm["json"]["outputs"])
    assert fm["pptx"]["category"] == "presentation"


def test_every_input_can_keep_its_format():
    for ext, entry in format_map().items():
        assert ext in entry["outputs"], ext


def test_every_listed_output_has_a_converter():
    for src, entry in format_map().items():
        for dst in entry["outputs"]:
            if dst != src:
                assert find(src, dst) is not None, f"{src} -> {dst}"


def test_json_to_yaml_uses_data_converter_and_json_to_csv_uses_sheets():
    assert find("json", "yaml").category == "data"
    assert find("json", "csv").category == "spreadsheet"
