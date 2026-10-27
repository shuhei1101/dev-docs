"""Markdown の埋め込みのマーカーの展開。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dev_docs.features.convert.markdown import render_table
from dev_docs.features.documents.fields import get_field
from dev_docs.shared.errors import InvalidArgumentError
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

EMBED_PATTERN = r"<!--\s*embed:\s*(?P<path>[^#\s]+)(?:#(?P<item>\S+))?\s*-->"

FENCE = re.compile(r"^\s{0,3}(?P<mark>`{3,}|~{3,})")
MISSING = object()


def _warning(message: str) -> str:
    """`> [!WARNING]` の囲みにする。"""
    return f"> [!WARNING]\n> 埋め込めません: {message}"


def _render(path: str, item: str | None, base: Path) -> str:
    """マーカー 1 つを、指した値の Markdown にする。"""
    root = base.resolve()
    target = (base / path).resolve()
    if not target.is_relative_to(root):
        return _warning(f"{path}（配信元の外を指しています）")
    if not target.is_file():
        return _warning(f"{path}（ファイルがありません）")
    try:
        data: Any = load_yaml(target.read_text(encoding="utf-8"), file=path)
    except (OSError, UnicodeDecodeError, YamlLoadError) as error:
        return _warning(f"{path}（{error}）")
    value: Any = data
    if item is not None:
        try:
            value = get_field(data, item, default=MISSING) if isinstance(data, dict) else MISSING
        except InvalidArgumentError as error:
            return _warning(f"{path}#{item}（{error}）")
        if value is MISSING:
            return _warning(f"{path}#{item} がありません")
    key = f"embed:{path}#{item}" if item is not None else f"embed:{path}"
    if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
        return render_table(value, {}, table_key=key)
    if isinstance(value, dict):
        rows = [{"キー": name, "値": cell} for name, cell in value.items()]
        return render_table(rows, {}, table_key=key)
    if isinstance(value, list):
        return "\n".join(f"- {entry}" for entry in value)
    return "" if value is None else str(value)


def expand_embeds(markdown: str, base: Path) -> str:
    """Markdown の中の埋め込みのマーカーを、指した YAML の値の表に置き換える。"""
    pattern = re.compile(EMBED_PATTERN)
    output: list[str] = []
    fence: str | None = None
    for line in markdown.splitlines(keepends=True):
        opened = FENCE.match(line)
        if fence is None and opened:
            fence = opened.group("mark")
        elif (
            fence is not None
            and opened
            and opened.group("mark")[0] == fence[0]
            and len(opened.group("mark")) >= len(fence)
        ):
            fence = None
        elif fence is None:
            matched = pattern.fullmatch(line.strip())
            if matched:
                ending = "\n" if line.endswith("\n") else ""
                output.append(_render(matched.group("path"), matched.group("item"), base) + ending)
                continue
        output.append(line)
    return "".join(output)
