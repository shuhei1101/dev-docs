from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from dev_docs.server.error_handlers import register_error_handlers
from dev_docs.shared.errors import UnknownSourceError, ValidationFailedError, Violation


class HiddenBody(BaseModel):
    """列の設定の本文の例。"""

    hidden: list[str]


class FakeTemplates:
    """描いたテンプレートの名前を記録する画面のテンプレートの偽物。"""

    def __init__(self) -> None:
        self.names: list[str] = []

    def TemplateResponse(self, request: Any, name: str, context: dict[str, Any]) -> HTMLResponse:
        self.names.append(name)
        return HTMLResponse("見つからない画面", status_code=404)


def test_register_error_handlers() -> None:
    """DevDocsError を problem+json にする（正常系）。"""
    # 準備
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/boom")
    def boom() -> None:
        raise ValidationFailedError(
            message="検査に通りません", violations=[Violation(path="name", rule="必須")]
        )

    client = TestClient(app)
    # 実行
    response = client.post("/boom")
    # 検証
    body = response.json()
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert body["type"] == "urn:dev-docs:error:ValidationFailedError"
    assert body["errors"] == [{"path": "name", "reason": "必須"}]


def test_register_error_handlers_when_request_invalid() -> None:
    """本文の型の誤りを 400 にする（正常系）。"""
    # 準備
    app = FastAPI()
    register_error_handlers(app)

    @app.put("/columns")
    def columns(body: HiddenBody) -> None:
        return None

    client = TestClient(app)
    # 実行
    response = client.put("/columns", json={"hidden": "x"})
    # 検証
    assert response.status_code == 400
    assert response.json()["errors"][0]["path"] == "hidden"


def test_register_error_handlers_when_html(
    make_handlers: Callable[..., Any], make_registry: Callable[..., Any]
) -> None:
    """画面は HTML で返す（正常系）。"""
    # 準備
    app = FastAPI()
    templates = FakeTemplates()
    app.state.handlers = make_handlers(registry=make_registry(), templates=templates)
    register_error_handlers(app)

    @app.get("/{source}/")
    def page(source: str) -> None:
        raise UnknownSourceError(message="配信元がありません", source_id=source)

    client = TestClient(app)
    # 実行
    response = client.get("/none/", headers={"Accept": "text/html"})
    # 検証
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert templates.names == ["not_found.html"]
