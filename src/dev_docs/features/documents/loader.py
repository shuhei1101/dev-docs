"""文書のファイルの収集と読み込み。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dev_docs.features.documents.types import Document, LoadProblem
from dev_docs.features.history.types import FileDates
from dev_docs.features.sources.types import DocumentTable

SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv"})


def collect_files(root: Path, patterns: Sequence[str]) -> list[str]:
    """文書の行の `paths` に当たるファイルを配信元の直下から集める。"""
    raise NotImplementedError


def split_front_matter(text: str, *, file: str | None = None) -> tuple[dict[str, Any], str]:
    """Markdown の先頭の front matter と本文を分ける。"""
    raise NotImplementedError


def load_file(
    root: Path,
    path: str,
    table: DocumentTable,
    *,
    source_id: str,
    dates: Mapping[str, FileDates] | None = None,
) -> tuple[list[Document], list[LoadProblem]]:
    """1 つのファイルを読み、文書の行に従って 1 件以上の文書にする。"""
    raise NotImplementedError


def documents_from_text(
    text: str,
    root: Path,
    path: str,
    table: DocumentTable,
    *,
    source_id: str,
    dates: Mapping[str, FileDates] | None = None,
) -> tuple[list[Document], list[LoadProblem]]:
    """1 つのファイルの内容の文字列を、文書の行に従って 1 件以上の文書にする。"""
    raise NotImplementedError
