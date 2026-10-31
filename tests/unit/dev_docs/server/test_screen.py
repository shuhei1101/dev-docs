from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.server.error_handlers import register_error_handlers
from dev_docs.server.screen import build_screen_router

INDEX = "<html>index</html>"


def _client(dist_dir: Path) -> TestClient:
    """画面の配信だけを持つアプリのクライアントを返す。"""
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_screen_router(dist_dir))
    return TestClient(app)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """index.html と assets の JS を置いたビルドのフォルダ。"""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path.parent / "secret").write_text("secret", encoding="utf-8")
    return tmp_path


def test_build_screen_router(dist_dir: Path) -> None:
    """文書の URL に index.html を返す（正常系）。"""
    # 準備
    client = _client(dist_dir)
    # 実行
    response = client.get("/default/設計書/a.md")
    # 検証
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["cache-control"] == "no-cache"


def test_build_screen_router_when_asset(dist_dir: Path) -> None:
    """assets のファイルを長く持たせて返す（正常系）。"""
    # 準備
    client = _client(dist_dir)
    # 実行
    response = client.get("/assets/index-abc.js")
    # 検証
    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_build_screen_router_when_asset_missing(dist_dir: Path) -> None:
    """無い assets と外へ出るパスを 404 にする（異常系）。"""
    # 準備
    client = _client(dist_dir)
    # 実行
    missing = client.get("/assets/none.js")
    escaping = client.get("/assets/..%2F..%2Fsecret")
    # 検証
    assert missing.status_code == 404
    assert missing.text != INDEX
    assert escaping.status_code == 404
    assert "secret" not in escaping.text


@pytest.mark.parametrize("path", ["/_api/none", "/mcp/none", "/_admin/none"])
def test_build_screen_router_when_excluded(dist_dir: Path, path: str) -> None:
    """API・MCP の頭のパスに画面を返さない（異常系）。"""
    # 準備
    client = _client(dist_dir)
    # 実行
    response = client.get(path)
    # 検証
    assert response.status_code == 404
    assert response.text != INDEX


def test_build_screen_router_when_build_missing(tmp_path: Path) -> None:
    """ビルドが無いと 503（異常系）。"""
    # 準備
    client = _client(tmp_path)
    # 実行
    response = client.get("/")
    # 検証
    body = response.json()
    assert response.status_code == 503
    assert body["type"] == "urn:dev-docs:error:ScreenBuildMissingError"
    assert any("vite build" in step for step in body["nextSteps"])
