from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from dev_docs.server.error_handlers import register_error_handlers
from dev_docs.shared.errors import DevDocsError, ValidationFailedError, Violation


class HiddenBody(BaseModel):
    """列の設定の本文の例。"""

    hidden: list[str]


@dataclass(kw_only=True)
class _SnakeError(DevDocsError):
    """snake_case のキーを持つ詳細を返す例外。"""

    status: ClassVar[int] = 400
    settings_path: str = "x"
    missing: dict[str, str] = field(default_factory=lambda: {"source_id": "a"})
    candidates: dict[str, list[str]] = field(
        default_factory=lambda: {"tests/test_main": ["rule-auth"]}
    )


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


def test_register_error_handlers_when_http_error() -> None:
    """ルートの無いパスを problem+json の 404 にする（正常系）。"""
    # 準備
    app = FastAPI()
    register_error_handlers(app)
    client = TestClient(app)
    # 実行
    response = client.get("/_api/none")
    # 検証
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "urn:dev-docs:error:HttpError"


def test_register_error_handlers_when_details_snake() -> None:
    """詳細のキーを camelCase にする（正常系）。"""
    # 準備
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise _SnakeError(message="失敗")

    client = TestClient(app)
    # 実行
    response = client.get("/boom")
    # 検証
    body = response.json()
    assert body["settingsPath"] == "x"
    assert body["missing"] == {"sourceId": "a"}
    assert body["candidates"] == {"tests/test_main": ["rule-auth"]}
    assert "nextSteps" in body
    assert not any("_" in key for key in body)
