"""Markdown の埋め込みのマーカーの展開。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from dev_docs.features.convert.markdown import render_table
from dev_docs.features.documents.fields import get_field
from dev_docs.shared.errors import InvalidArgumentError

EMBED_PATTERN = r"<!--\s*embed:\s*(?P<path>[^#\s]+)(?:#(?P<item>\S+))?\s*-->"

FENCE = re.compile(r"^\s{0,3}(?P<mark>`{3,}|~{3,})")
MISSING = object()


def _warning(message: str) -> str:
    """`> [!WARNING]` の囲みにする。"""
    return f"> [!WARNING]\n> 埋め込めません: {message}"


def _render(path: str, item: str | None, embedded: Mapping[str, Any | None]) -> str:
    """マーカー 1 つを、指した値の Markdown にする。"""
    data = embedded.get(path)
    if data is None:
        return _warning(path)
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


def _markers(markdown: str) -> list[tuple[str, re.Match[str] | None]]:
    """行ごとに、コードブロックの外のマーカーに該当すればその一致を添えて並べる。"""
    pattern = re.compile(EMBED_PATTERN)
    result: list[tuple[str, re.Match[str] | None]] = []
    fence: str | None = None
    for line in markdown.splitlines(keepends=True):
        opened = FENCE.match(line)
        matched: re.Match[str] | None = None
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
        result.append((line, matched))
    return result


def _outside(path: str) -> bool:
    """配信元の外を指すパス（`..` の要素を持つか `/` で始まる）か。"""
    return path.startswith("/") or ".." in PurePosixPath(path).parts


def embed_paths(markdown: str) -> list[str]:
    """Markdown のコードブロックの外にある埋め込みのマーカーのパスを、出る順に重ねずに返却する。"""
    paths: list[str] = []
    for _, matched in _markers(markdown):
        if matched is None:
            continue
        path = matched.group("path")
        if not _outside(path) and path not in paths:
            paths.append(path)
    return paths


def expand_embeds(markdown: str, embedded: Mapping[str, Any | None]) -> str:
    """Markdown の中の埋め込みのマーカーを、指した文書の値の表に置き換える。"""
    output: list[str] = []
    for line, matched in _markers(markdown):
        if matched is None:
            output.append(line)
            continue
        ending = "\n" if line.endswith("\n") else ""
        output.append(_render(matched.group("path"), matched.group("item"), embedded) + ending)
    return "".join(output)
