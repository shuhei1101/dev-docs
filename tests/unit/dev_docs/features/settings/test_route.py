from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.features.settings.route import build_settings_router
from dev_docs.server.error_handlers import register_error_handlers

from ...conftest import FakeIndex

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
PUT_BODY = {"sources": [{"id": "a", "config": "/tmp/a/project-index.yaml"}]}


def _item(row: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    """project-index の端末の設定の取得の `sources[]` の 1 件（行の値に状態を重ねたもの）を作る。"""
    return {
        "enabled": True,
        "scope": {"read": [], "write": None},
        "outsideRead": True,
        **row,
        "status": status,
        "errors": [],
        "configVersion": None,
        **extra,
    }


def _client(make_handlers: Callable[..., Any]) -> TestClient:
    """設定のルートと例外のハンドラを持つアプリの TestClient を作る。"""
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_settings_router(make_handlers()))
    return TestClient(app)


def test_build_settings_router_when_get(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """行に状態を重ねる（正常系）。"""
    # 準備
    fake_index.settings = {
        "settingsPath": "/pi/settings.yaml",
        "sources": [
            _item({"id": "a", "config": ["/tmp/a/project-index.yaml"]}, "serving"),
            _item(
                {"id": "b", "config": ["/tmp/b/project-index.yaml"]},
                "not_served",
                errors=[{"path": "documents[0].paths", "reason": "必須のキーが無い"}],
            ),
        ],
    }
    # 実行
    response = _client(make_handlers).get("/_api/settings/sources")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["settingsPath"] == "/pi/settings.yaml"
    assert [(row["id"], row["status"]) for row in body["sources"]] == [
        ("a", "serving"),
        ("b", "not_served"),
    ]
    assert body["sources"][1]["errors"] == [
        {"path": "documents[0].paths", "reason": "必須のキーが無い"}
    ]


def test_build_settings_router_when_put(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """保存を依頼して状態を返す（正常系）。"""
    # 準備（偽物は保存した行を、続く端末の設定の取得で返す）
    # 実行
    response = _client(make_handlers).put(
        "/_api/settings/sources", json=PUT_BODY, headers=SAME_ORIGIN
    )
    # 検証
    put = next(request for request in fake_index.requests if request.method == "PUT")
    sent = json.loads(put.content)
    assert response.status_code == 200
    assert response.json()["sources"][0]["status"] == "serving"
    assert sent["sources"][0]["config"] == ["/tmp/a/project-index.yaml"]


def test_build_settings_router_when_pending_reload(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """読み直していない行（正常系）。"""
    # 準備
    fake_index.settings = {
        "settingsPath": "/pi/settings.yaml",
        "sources": [
            _item({"id": "a", "config": ["/a"]}, "serving"),
            _item({"id": "b", "config": ["/b"]}, "serving"),
            _item({"id": "fresh", "config": ["/fresh"]}, "pending_reload"),
        ],
    }
    # 実行
    response = _client(make_handlers).get("/_api/settings/sources")
    # 検証
    assert response.status_code == 200
    assert response.json()["sources"][2]["status"] == "pending_reload"


def test_build_settings_router_when_rejected(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index が行を受け付けない（異常系）。"""
    # 準備
    fake_index.responses[("PUT", "/settings/sources")] = (
        422,
        {"detail": "検証に失敗", "errors": [{"path": "sources[0].config", "reason": "無い"}]},
    )
    # 実行
    response = _client(make_handlers).put(
        "/_api/settings/sources", json=PUT_BODY, headers=SAME_ORIGIN
    )
    # 検証
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"] == [{"path": "sources[0].config", "reason": "無い"}]


def test_build_settings_router_when_unexpected_status(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index が予期しないステータスを返す（異常系）。"""
    # 準備
    fake_index.responses[("PUT", "/settings/sources")] = (500, "boom")
    # 実行
    response = _client(make_handlers).put(
        "/_api/settings/sources", json=PUT_BODY, headers=SAME_ORIGIN
    )
    # 検証
    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"


def test_build_settings_router_when_unreachable(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    fake_index.refused = True
    client = _client(make_handlers)
    # 実行
    responses = [
        client.get("/_api/settings/sources"),
        client.put("/_api/settings/sources", json=PUT_BODY, headers=SAME_ORIGIN),
    ]
    # 検証
    assert [response.status_code for response in responses] == [503, 503]
    assert [sorted(response.json()["projectIndex"]) for response in responses] == [
        ["address", "reason"],
        ["address", "reason"],
    ]
