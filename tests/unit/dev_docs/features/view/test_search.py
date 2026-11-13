from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from dev_docs.features.view.search import screen_search
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexUnreachableError

from ...conftest import FakeIndex, config_json, doc_json


def test_screen_search(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """文書のページのパスにする（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(
        "sample",
        documents=[
            {"id": "rules", "paths": ["docs/*.yaml"], "schema": {}},
            {"id": "notes", "paths": ["notes/files.yaml"], "schema": {}, "records": "files"},
        ],
    )
    fake_index.docs["sample"] = {
        None: [
            doc_json("a", "docs/a.yaml"),
            doc_json("n-1", "notes/files.yaml", kind="notes"),
        ]
    }
    fake_index.search_results = {
        "totalCount": 5,
        "items": [
            {
                "path": "docs/a",
                "id": "a",
                "filePath": "docs/a.yaml",
                "name": "A",
                "snippets": ["foo"],
            },
            {
                "path": "notes/files",
                "id": "n-1",
                "filePath": "notes/files.yaml",
                "name": "N",
                "snippets": [],
            },
        ],
    }
    # 実行
    result = asyncio.run(screen_search(make_client(), "sample", "foo", ref=None, limit=20))
    # 検証
    assert [item.path for item in result.items] == ["docs/a", "notes/files/n-1"]
    assert result.total_count == 5
    listed = next(request for request in fake_index.requests if request.url.path.endswith("/docs"))
    assert "values" not in listed.url.params


def test_screen_search_when_unreachable(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    fake_index.refused = True
    # 実行・検証
    with pytest.raises(ProjectIndexUnreachableError):
        asyncio.run(screen_search(make_client(), "sample", "foo", ref=None, limit=20))
