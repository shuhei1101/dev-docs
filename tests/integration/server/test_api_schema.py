from __future__ import annotations

from collections.abc import Callable
from typing import Any

EXPECTED_OPERATION_IDS = [
    "settings-get_settings_sources",
    "settings-put_settings_sources",
    "view-get_document",
    "view-get_document_default",
    "view-list_refs",
    "view-put_columns",
    "view-search_page",
]


def test_normal(make_source: Callable[..., Any], make_server: Callable[..., Any]) -> None:
    """画面の API だけを載せたスキーマを返す（正常系）。"""
    # 準備
    env = make_server(make_source("sample"))
    # 実行
    response = env.client.get("/_api/openapi.json")
    # 検証
    body = response.json()
    paths = body["paths"]
    operation_ids = [
        operation["operationId"] for item in paths.values() for operation in item.values()
    ]
    document_properties = body["components"]["schemas"]["DocumentResponse"]["properties"]
    assert response.status_code == 200
    assert all(path.startswith("/_api/") for path in paths)
    assert "/mcp" not in paths
    assert "/_admin/mcp" not in paths
    assert "/_api/openapi.json" not in paths
    assert sorted(operation_ids) == EXPECTED_OPERATION_IDS
    assert len(set(operation_ids)) == len(operation_ids)
    assert "conversionError" in document_properties
    assert "tableKeys" in document_properties
    assert "conversion_error" not in document_properties
