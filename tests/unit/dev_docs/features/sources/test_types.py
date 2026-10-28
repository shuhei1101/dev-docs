from __future__ import annotations

from collections.abc import Callable

import pytest

from dev_docs.features.sources.types import DocumentTable, ServedSource, SourceConfig
from dev_docs.shared.errors import UnknownKindError


def test_served_source_table(
    make_served_source: Callable[..., ServedSource],
    make_source_config: Callable[..., SourceConfig],
) -> None:
    """行を引く（正常系）。"""
    # 準備
    documents = [
        DocumentTable(id="rules", type="yaml", paths=["docs/rule/*.yaml"]),
        DocumentTable(id="notes", type="markdown", paths=["docs/note/*.md"]),
    ]
    source = make_served_source(config=make_source_config(documents=documents))
    # 実行
    result = source.table("notes")
    # 検証
    assert result.id == "notes"


def test_served_source_table_when_unknown(
    make_served_source: Callable[..., ServedSource],
    make_source_config: Callable[..., SourceConfig],
) -> None:
    """無い種類（異常系）。"""
    # 準備
    documents = [
        DocumentTable(id="rules", type="yaml", paths=["docs/rule/*.yaml"]),
        DocumentTable(id="notes", type="markdown", paths=["docs/note/*.md"], enabled=False),
    ]
    source = make_served_source(config=make_source_config(documents=documents))
    # 実行・検証
    with pytest.raises(UnknownKindError) as exc_info:
        source.table("x")
    assert exc_info.value.kinds == ["rules"]
