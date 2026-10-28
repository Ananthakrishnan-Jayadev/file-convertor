"""Converter registry: each converter declares which input extensions it reads and
which output extensions it can produce. Lookup goes in registration order."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# A converter reads `src` and writes its result into `out_dir`, returning the path it
# wrote. Converters that produce several files (PDF pages, workbook sheets) return a zip.
ConvertFn = Callable[[Path, Path, str], Path]

ALIASES = {
    "jpeg": "jpg", "jpe": "jpg", "tif": "tiff", "heif": "heic", "htm": "html",
    "yml": "yaml", "markdown": "md",
}


@dataclass(frozen=True)
class Converter:
    category: str
    inputs: frozenset[str]
    outputs: frozenset[str]
    fn: ConvertFn


_converters: list[Converter] = []


def register(category: str, inputs: set[str], outputs: set[str]):
    def deco(fn: ConvertFn) -> ConvertFn:
        _converters.append(Converter(category, frozenset(inputs), frozenset(outputs), fn))
        return fn
    return deco


def normalize(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return ALIASES.get(ext, ext)


def find(src_ext: str, dst_ext: str) -> Converter | None:
    for c in _converters:
        if src_ext in c.inputs and dst_ext in c.outputs:
            return c
    return None


def format_map() -> dict[str, dict]:
    """{input_ext: {"category": ..., "outputs": [...]}}. The input format itself is always
    listed as an output, meaning "keep the format, only shrink it"."""
    result: dict[str, dict] = {}
    for c in _converters:
        for ext in c.inputs:
            entry = result.setdefault(ext, {"category": c.category, "outputs": {ext}})
            entry["outputs"] |= c.outputs
    return {
        ext: {"category": e["category"], "outputs": sorted(e["outputs"])}
        for ext, e in sorted(result.items())
    }
