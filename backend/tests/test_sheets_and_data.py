import json
import zipfile

import pandas as pd
import xmltodict
import yaml

from app.converters.data import convert_data
from app.converters.sheets import convert_sheet


def test_csv_to_xlsx_keeps_values(csv_file, out_dir):
    dst = convert_sheet(csv_file, out_dir, "xlsx")
    df = pd.read_excel(dst)
    assert list(df.columns) == ["name", "age", "city"]
    assert df["age"].tolist() == [31, 45, 28]
    assert df["city"].iloc[2] == "Montréal"


def test_csv_to_ods_and_back(csv_file, out_dir, tmp_path):
    ods = convert_sheet(csv_file, out_dir, "ods")
    back = tmp_path / "back"
    back.mkdir()
    csv = convert_sheet(ods, back, "csv")
    assert "Chloé" in csv.read_text(encoding="utf-8-sig")


def test_semicolon_csv_is_detected(tmp_path, out_dir):
    src = tmp_path / "euro.csv"
    src.write_text("a;b\n1;2\n3;4\n", encoding="utf-8")
    df = pd.read_excel(convert_sheet(src, out_dir, "xlsx"))
    assert list(df.columns) == ["a", "b"]


def test_windows_encoded_csv(tmp_path, out_dir):
    src = tmp_path / "legacy.csv"
    src.write_bytes("name\nCafé\n".encode("cp1252"))
    df = pd.read_excel(convert_sheet(src, out_dir, "xlsx"))
    assert df["name"].iloc[0] == "Café"


def test_single_column_csv_is_not_split(tmp_path, out_dir):
    src = tmp_path / "names.csv"
    src.write_text("name\nAnna\nNoah\n", encoding="utf-8")
    df = pd.read_excel(convert_sheet(src, out_dir, "xlsx"))
    assert list(df.columns) == ["name"]
    assert df["name"].tolist() == ["Anna", "Noah"]


def test_pipe_delimited_csv(tmp_path, out_dir):
    src = tmp_path / "export.csv"
    src.write_text("id|label\n1|one\n2|two\n", encoding="utf-8")
    df = pd.read_excel(convert_sheet(src, out_dir, "xlsx"))
    assert list(df.columns) == ["id", "label"]


def test_multi_sheet_xlsx_to_csv_is_zip_of_sheets(xlsx_two_sheets, out_dir):
    dst = convert_sheet(xlsx_two_sheets, out_dir, "csv")
    assert dst.suffix == ".zip"
    with zipfile.ZipFile(dst) as zf:
        assert sorted(zf.namelist()) == ["First.csv", "Second.csv"]


def test_multi_sheet_xlsx_json_roundtrip(xlsx_two_sheets, out_dir, tmp_path):
    js = convert_sheet(xlsx_two_sheets, out_dir, "json")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["First"] == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    back = tmp_path / "back"
    back.mkdir()
    xlsx = convert_sheet(js, back, "xlsx")
    assert set(pd.read_excel(xlsx, sheet_name=None)) == {"First", "Second"}


def test_csv_to_tsv_and_html(csv_file, out_dir):
    assert "Asha\t31" in convert_sheet(csv_file, out_dir, "tsv").read_text(encoding="utf-8")
    assert "<table" in convert_sheet(csv_file, out_dir, "html").read_text(encoding="utf-8")


def test_json_yaml_roundtrip(tmp_path, out_dir):
    src = tmp_path / "config.json"
    payload = {"name": "app", "ports": [80, 443], "debug": False}
    src.write_text(json.dumps(payload))
    y = convert_data(src, out_dir, "yaml")
    assert yaml.safe_load(y.read_text(encoding="utf-8")) == payload


def test_json_list_to_xml_gets_a_root(tmp_path, out_dir):
    src = tmp_path / "items.json"
    src.write_text(json.dumps([{"id": 1}, {"id": 2}]))
    xml = convert_data(src, out_dir, "xml")
    parsed = xmltodict.parse(xml.read_text(encoding="utf-8"))
    assert [i["id"] for i in parsed["root"]["item"]] == ["1", "2"]


def test_xml_to_json(tmp_path, out_dir):
    src = tmp_path / "note.xml"
    src.write_text("<note><to>Ana</to><body>Hi</body></note>")
    data = json.loads(convert_data(src, out_dir, "json").read_text(encoding="utf-8"))
    assert data == {"note": {"to": "Ana", "body": "Hi"}}
