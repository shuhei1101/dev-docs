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


def test_screen_search_when_excluded(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """検索から除外される文書（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(
        "sample", documents=[{"id": "rules", "paths": ["docs/*.yaml"], "schema": {}}]
    )
    fake_index.docs["sample"] = {None: [doc_json("a", "docs/a.yaml")]}
    item = {"path": "docs/a", "id": "a", "filePath": "docs/a.yaml", "name": "A", "snippets": []}
    client = make_client()
    # 実行
    fake_index.search_results = {"totalCount": 1, "items": [item | {"excluded": True}]}
    included = asyncio.run(
        screen_search(client, "sample", "a", ref=None, limit=20, include_excluded=True)
    )
    included_params = [
        request.url.params
        for request in fake_index.requests
        if request.url.path.endswith("/search")
    ][-1]
    fake_index.search_results = {"totalCount": 0, "items": [], "excludedCount": 1}
    default = asyncio.run(screen_search(client, "sample", "a", ref=None, limit=20))
    default_params = [
        request.url.params
        for request in fake_index.requests
        if request.url.path.endswith("/search")
    ][-1]
    # 検証
    assert included_params["include_excluded"] == "true"
    assert "include_excluded" not in default_params
    assert included.items[0].excluded is True
    assert included.excluded_count == 0
    assert default.excluded_count == 1


def test_screen_search_when_match_count(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """一致した行の数（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(
        "sample", documents=[{"id": "rules", "paths": ["docs/*.yaml"], "schema": {}}]
    )
    fake_index.docs["sample"] = {None: [doc_json("a", "docs/a.yaml"), doc_json("b", "docs/b.yaml")]}
    fake_index.search_results = {
        "totalCount": 2,
        "items": [
            {
                "path": "docs/a",
                "id": "a",
                "filePath": "docs/a.yaml",
                "name": "A",
                "snippets": [],
                "matchCount": 4,
            },
            {"path": "docs/b", "id": "b", "filePath": "docs/b.yaml", "name": "B", "snippets": []},
        ],
    }
    # 実行
    result = asyncio.run(screen_search(make_client(), "sample", "foo", ref=None, limit=20))
    # 検証
    assert [item.match_count for item in result.items] == [4, None]
