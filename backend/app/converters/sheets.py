import csv
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from ..registry import normalize, register

SHEET_IN = {"csv", "tsv", "xlsx", "xls", "ods", "json"}
SHEET_OUT = {"csv", "tsv", "xlsx", "ods", "json", "html"}


DELIMITERS = ",;\t|"
SNIFF_CHARS = 20_000


# A plain number: optional sign, digits, optional decimals or exponent.
NUMBER = r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?"
# Looks like a number but must stay text: leading zeros (00123, 007) or too many digits for
# Excel to hold exactly (card numbers, long IDs).
KEEP_AS_TEXT = r"[+-]?0\d.*|.*\d{16,}.*"


def _decode(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):  # Excel's "Unicode Text" export is UTF-16
        return raw.decode("utf-16")
    # latin-1 accepts any byte sequence, so this always returns something.
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _sniff_delimiter(sample: str) -> str:
    # Limit the sniffer to real delimiters: left unrestricted it happily picks a letter
    # in single-column files (e.g. "n" in "name\nCafé").
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except csv.Error:
        return ","


def _numbers_where_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Turn a text column into numbers only when every value is a plain number and none
    would lose information, so 00123 or a 16-digit ID stays exactly as written."""
    for col in df.columns:
        values = df[col].dropna().astype(str).str.strip()
        if values.empty or not values.str.fullmatch(NUMBER).all() or values.str.fullmatch(KEEP_AS_TEXT).any():
            continue
        df[col] = pd.to_numeric(df[col])
    return df


def read_sheets(src: Path, ext: str) -> dict[str, pd.DataFrame]:
    if ext in ("csv", "tsv"):
        text = _decode(src.read_bytes())
        sep = "\t" if ext == "tsv" else _sniff_delimiter(text[:SNIFF_CHARS])
        # Read everything as text, with only empty cells as missing ("NA" or "null" stay as typed),
        # then convert the columns that are safely numeric.
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False, na_values=[""])
        return {src.stem: _numbers_where_safe(df)}
    if ext == "json":
        data = json.loads(src.read_text(encoding="utf-8-sig"))
        # {"Sheet1": [...], "Sheet2": [...]} is how we write multi-sheet JSON, so read it back the same way.
        if isinstance(data, dict) and data and all(isinstance(v, list) for v in data.values()):
            return {name: pd.json_normalize(rows) for name, rows in data.items()}
        return {src.stem: pd.json_normalize(data)}
    engine = {"xls": "xlrd", "ods": "odf"}.get(ext, "openpyxl")
    return pd.read_excel(src, sheet_name=None, engine=engine)


def _write_one(df: pd.DataFrame, path: Path, fmt: str) -> None:
    if fmt == "csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")  # BOM so Excel reads UTF-8 correctly
    elif fmt == "tsv":
        df.to_csv(path, index=False, sep="\t", encoding="utf-8")
    elif fmt == "html":
        df.to_html(path, index=False, na_rep="")


@register("spreadsheet", SHEET_IN, SHEET_OUT)
def convert_sheet(src: Path, out_dir: Path, fmt: str) -> Path:
    sheets = read_sheets(src, normalize(src.suffix))

    if fmt in ("xlsx", "ods"):
        dst = out_dir / f"{src.stem}.{fmt}"
        engine = "odf" if fmt == "ods" else "openpyxl"
        with pd.ExcelWriter(dst, engine=engine) as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name[:31] or "Sheet1", index=False)
        return dst

    if fmt == "json":
        dst = out_dir / f"{src.stem}.json"
        records = {name: json.loads(df.to_json(orient="records", date_format="iso")) for name, df in sheets.items()}
        payload = next(iter(records.values())) if len(records) == 1 else records
        dst.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return dst

    # CSV/TSV/HTML hold a single table, so a multi-sheet workbook becomes a zip of files.
    if len(sheets) == 1:
        dst = out_dir / f"{src.stem}.{fmt}"
        _write_one(next(iter(sheets.values())), dst, fmt)
        return dst
    dst = out_dir / f"{src.stem}-{fmt}.zip"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in sheets.items():
            part = out_dir / f"{name}.{fmt}"
            _write_one(df, part, fmt)
            zf.write(part, part.name)
            part.unlink()
    return dst
