from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from dev_docs.server.error_handlers import register_error_handlers
from dev_docs.shared.errors import ValidationFailedError, Violation


class HiddenBody(BaseModel):
    """列の設定の本文の例。"""

    hidden: list[str]


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
