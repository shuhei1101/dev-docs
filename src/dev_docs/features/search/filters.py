"""検索の条件の確かめと照合。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from dev_docs.features.documents.types import Document
from dev_docs.features.search.types import Condition, Group, SearchRequest
from dev_docs.shared.errors import Violation


def check_filter(request: SearchRequest, fields: Mapping[str, str]) -> list[Violation]:
    """条件・並べ替え・集計の項目と値が使えるかを確かめる。"""
    raise NotImplementedError


def parse_compare_value(value: str, field_type: str, *, today: date) -> Any:
    """条件の値を項目の型で解釈する。"""
    raise NotImplementedError


def match_filter(
    node: Condition | Group | None,
    document: Document,
    *,
    fields: Mapping[str, str],
    today: date,
) -> bool:
    """文書が条件の木に当たるかを判定する。"""
    raise NotImplementedError


def match_words(document: Document, words: Sequence[str]) -> bool:
    """空白で区切った語を全て含む文書かを判定する。"""
    raise NotImplementedError


def snippet_lines(
    text: str, words: Sequence[str], *, context_lines: int, max_count: int
) -> list[str]:
    """本文から語を含む行と前後の行を抜き出す。"""
    raise NotImplementedError
