from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.features.metadata.route import build_metadata_router
from dev_docs.server.error_handlers import register_error_handlers

from ...conftest import FakeIndex, config_json

COMMIT_BODY = {
    "edits": [
        {
            "key": "tags:n1:update",
            "kind": "tags",
            "op": "update",
            "docId": "n1",
            "docKind": "note",
            "expectedVersion": "c3d4e5",
            "values": {"tags": ["topic:a"]},
        }
    ],
    "message": "タグを修正する",
}


def _client(make_handlers: Callable[..., Any]) -> TestClient:
    """メタデータのルートと例外のハンドラを持つアプリの TestClient を作る。"""
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_metadata_router(make_handlers()))
    return TestClient(app)


def test_build_metadata_router_when_metadata(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """メタデータの取得（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(
        documents=[{"id": "note", "paths": ["notes/*.yaml"], "alias_type": "doc"}]
    )
    fake_index.docs["sample"] = {None: []}
    # 実行
    response = _client(make_handlers).get("/_api/sources/sample/metadata")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert [kind["id"] for kind in body["kinds"]] == [
        "terms",
        "aliases",
        "tags",
        "rules",
        "config",
        "files",
    ]
    assert {"canAdd", "canDelete", "createKind"} <= set(body["kinds"][0])


def test_build_metadata_router_when_cross_origin(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """別のオリジン（異常系）。"""
    # 準備
    client = _client(make_handlers)
    # 実行
    response = client.post(
        "/_api/sources/sample/commits",
        json=COMMIT_BODY,
        headers={"Origin": "http://127.0.0.1:9999"},
    )
    # 検証
    assert response.status_code == 403
    assert fake_index.requests == []
