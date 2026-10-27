from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from dev_docs.features.settings import route as route_module
from dev_docs.features.settings.route import build_settings_router
from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import SourceStatus
from dev_docs.shared.errors import Violation


class FakeTemplates:
    """描いたテンプレートの名前と値を記録する画面のテンプレートの偽物。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def TemplateResponse(self, request: Any, name: str, context: dict[str, Any]) -> HTMLResponse:
        self.calls.append((name, context))
        return HTMLResponse("ok")


class FakeRegistry(SourceRegistry):
    """決めた状態を返す配信元の一覧の偽物。"""

    def __init__(self, statuses: list[SourceStatus]) -> None:
        super().__init__()
        self._statuses = statuses

    def statuses(self) -> list[SourceStatus]:
        return self._statuses


def test_build_settings_router_when_root(make_handlers: Callable[..., Any]) -> None:
    """トップを転送する（正常系）。"""
    # 準備
    app = FastAPI()
    app.include_router(build_settings_router(make_handlers()))
    client = TestClient(app, follow_redirects=False)
    # 実行
    response = client.get("/")
    # 検証
    assert response.status_code == 302
    assert response.headers["location"] == "/_settings/"


def test_build_settings_router_when_settings_page(
    make_handlers: Callable[..., Any],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
    make_status: Callable[..., SourceStatus],
) -> None:
    """設定画面に状態を埋め込む（正常系）。"""
    # 準備
    terminal = make_terminal_config(
        sources=[
            make_entry("/tmp/a/dev-docs.yaml", source_id="a"),
            make_entry("/tmp/b/dev-docs.yaml", source_id="b"),
        ]
    )
    statuses = [
        make_status("a", 0),
        make_status(
            "b",
            1,
            "not_served",
            errors=[Violation(path="documents[0].paths", rule="必須のキーが無い")],
        ),
    ]
    templates = FakeTemplates()
    handlers = make_handlers(
        terminal=terminal, registry=FakeRegistry(statuses), templates=templates
    )
    app = FastAPI()
    app.include_router(build_settings_router(handlers))
    client = TestClient(app)
    # 実行
    response = client.get("/_settings/")
    # 検証
    name, context = templates.calls[0]
    assert response.status_code == 200
    assert name == "settings.html"
    assert context["config_path"] == str(terminal.file)
    assert len(context["sources"]) == 2
    assert context["sources"][1]["status"] == "not_served"
    assert context["sources"][1]["errors"] == [
        {"path": "documents[0].paths", "reason": "必須のキーが無い"}
    ]


def test_build_settings_router_when_put(
    make_handlers: Callable[..., Any],
    make_status: Callable[..., SourceStatus],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """保存して状態を返す（正常系）。"""
    # 準備
    saved: list[list[SourceEntry]] = []

    def fake_save_sources(sources: list[SourceEntry], **kwargs: Any) -> list[SourceStatus]:
        saved.append(list(sources))
        return [make_status("a", 0)]

    monkeypatch.setattr(route_module, "save_sources", fake_save_sources)
    handlers = make_handlers(settings_lock=threading.Lock())
    app = FastAPI()
    app.include_router(build_settings_router(handlers))
    client = TestClient(app)
    body = {"sources": [{"id": "a", "config": ["/tmp/a/dev-docs.yaml"]}]}
    # 実行
    response = client.put(
        "/_api/settings/sources", json=body, headers={"Sec-Fetch-Site": "same-origin"}
    )
    # 検証
    assert response.status_code == 200
    assert response.json()["sources"][0]["status"] == "serving"
    assert saved[0][0].id == "a"
