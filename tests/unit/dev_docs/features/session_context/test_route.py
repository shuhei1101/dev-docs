from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.features.session_context.route import build_session_context_router
from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.main import build_handlers
from dev_docs.server.error_handlers import register_error_handlers


def _client(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> tuple[TestClient, Path]:
    """配信元 1 つの配線済みの関数でルーターを載せたクライアントと、配信元のフォルダを返す。"""
    config = make_source_dir("sample")
    handlers = build_handlers(
        make_terminal_config(sources=[make_entry(str(config), source_id="sample")])
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url="/_api/openapi.json")
    register_error_handlers(app)
    app.include_router(build_session_context_router(handlers))
    return TestClient(app), config.parent


def test_build_session_context_router(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """本文を検証して組み立てた文脈を返す（正常系）。"""
    # 準備
    client, root = _client(make_source_dir, make_terminal_config, make_entry)
    # 実行
    response = client.post("/_admin/session-context", json={"cwd": str(root)})
    # 検証
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["sources"]] == ["sample"]


def test_build_session_context_router_when_invalid(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """入力の違反を 422 で返す（異常系）。"""
    # 準備
    client, root = _client(make_source_dir, make_terminal_config, make_entry)
    # 実行
    response = client.post("/_admin/session-context", json={"cwd": str(root), "reason": "unknown"})
    # 検証
    body = response.json()
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert any("reason" in item["path"] for item in body["errors"])


def test_build_session_context_router_when_schema(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """画面の API のスキーマに載らない（正常系）。"""
    # 準備
    client, _ = _client(make_source_dir, make_terminal_config, make_entry)
    # 実行
    response = client.get("/_api/openapi.json")
    # 検証
    assert response.status_code == 200
    assert "/_admin/session-context" not in response.json()["paths"]
