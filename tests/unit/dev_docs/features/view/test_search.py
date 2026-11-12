from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from dev_docs.features.view.search import screen_search
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexUnreachableError

from ...conftest import FakeIndex, config_json


def test_screen_search(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """文書のページのパスにする（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json("sample")
    fake_index.search_results = {
        "totalCount": 5,
        "items": [
            {"id": "a", "path": "docs/a.yaml", "name": "A", "snippets": ["foo"]},
            {
                "id": "n-1",
                "path": "notes/files.yaml",
                "name": "N",
                "snippets": [],
                "recordIndex": 0,
            },
        ],
    }
    # 実行
    result = asyncio.run(screen_search(make_client(), "sample", "foo", ref=None, limit=20))
    # 検証
    assert [item.path for item in result.items] == ["docs/a", "notes/files/n-1"]
    assert result.total_count == 5


def test_screen_search_when_unreachable(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    fake_index.refused = True
    # 実行・検証
    with pytest.raises(ProjectIndexUnreachableError):
        asyncio.run(screen_search(make_client(), "sample", "foo", ref=None, limit=20))
