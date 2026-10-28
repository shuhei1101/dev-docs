from __future__ import annotations

from collections.abc import Callable
from typing import Any

EXPECTED_OPERATION_IDS = [
    "get_document",
    "get_document_default",
    "get_settings_sources",
    "list_refs",
    "put_columns",
    "put_settings_sources",
    "search_page",
]


def test_normal(make_source: Callable[..., Any], make_server: Callable[..., Any]) -> None:
    """画面の API だけを載せたスキーマを返す（正常系）。"""
    # 準備
    env = make_server(make_source("sample"))
    # 実行
    response = env.client.get("/_api/openapi.json")
    # 検証
    paths = response.json()["paths"]
    operation_ids = [
        operation["operationId"] for item in paths.values() for operation in item.values()
    ]
    assert response.status_code == 200
    assert all(path.startswith("/_api/") for path in paths)
    assert "/mcp" not in paths
    assert "/_admin/mcp" not in paths
    assert "/_api/openapi.json" not in paths
    assert sorted(operation_ids) == EXPECTED_OPERATION_IDS
