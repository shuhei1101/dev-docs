"""Markdown の埋め込みのマーカーの展開。"""

from __future__ import annotations

from pathlib import Path

EMBED_PATTERN = r"<!--\s*embed:\s*(?P<path>[^#\s]+)(?:#(?P<item>\S+))?\s*-->"


def expand_embeds(markdown: str, base: Path) -> str:
    """Markdown の中の埋め込みのマーカーを、指した YAML の値の表に置き換える。"""
    raise NotImplementedError
