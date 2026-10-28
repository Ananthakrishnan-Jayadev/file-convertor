"""Structured data: JSON, YAML and XML."""

import json
from pathlib import Path

import xmltodict
import yaml

from ..registry import normalize, register


def _load(src: Path):
    text = src.read_text(encoding="utf-8-sig")
    match normalize(src.suffix):
        case "json":
            return json.loads(text)
        case "yaml":
            return yaml.safe_load(text)
        case "xml":
            return xmltodict.parse(text)


@register("data", {"json", "yaml", "xml"}, {"json", "yaml", "xml"})
def convert_data(src: Path, out_dir: Path, fmt: str) -> Path:
    data = _load(src)
    dst = out_dir / f"{src.stem}.{fmt}"
    match fmt:
        case "json":
            text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        case "yaml":
            text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        case "xml":
            # XML needs exactly one root element.
            if not (isinstance(data, dict) and len(data) == 1):
                data = {"root": {"item": data} if isinstance(data, list) else data}
            text = xmltodict.unparse(data, pretty=True)
    dst.write_text(text, encoding="utf-8")
    return dst
