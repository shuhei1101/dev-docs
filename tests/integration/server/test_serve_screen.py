from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .conftest import MockIndex, ServerEnv

INDEX_HTML = "<!doctype html><title>dev-docs</title><script src=/assets/app-1a2b3c.js></script>"
ASSET_JS = "console.log('screen');"


def _build_dir(tmp_path: Path, *, with_index: bool) -> Path:
    """`assets/` の JS 1 件と、`index.html`（`with_index` のとき）を配置したビルドのフォルダを作る。"""
    folder = tmp_path / "screen-build"
    (folder / "assets").mkdir(parents=True)
    (folder / "assets" / "app-1a2b3c.js").write_text(ASSET_JS, encoding="utf-8")
    if with_index:
        (folder / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return folder


def test_normal(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """画面のパスに index.html を、assets/ のパスに静的ファイルを返却する（正常系）。"""
    # 準備
    env = make_server(sample_index, screen_dir=_build_dir(tmp_path, with_index=True))
    # 実行
    top = env.client.get("/")
    doc = env.client.get("/sample/docs/doc-1")
    asset = env.client.get("/assets/app-1a2b3c.js")
    api = env.client.get("/_api/sources/sample/docs")
    # 検証
    for page in (top, doc):
        assert page.status_code == 200
        assert page.text == INDEX_HTML
        assert page.headers["content-type"].startswith("text/html")
        assert page.headers["cache-control"] == "no-cache"
    assert asset.status_code == 200
    assert asset.text == ASSET_JS
    assert "javascript" in asset.headers["content-type"]
    assert "immutable" in asset.headers["cache-control"]
    assert api.status_code == 200
    assert api.json()["source"] == "sample"


def test_error_when_not_found(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """assets/ の無いファイルと /_api/ の無いパスは index.html を返却せず 404 を返却する（異常系）。"""
    # 準備
    env = make_server(sample_index, screen_dir=_build_dir(tmp_path, with_index=True))
    # 実行
    asset = env.client.get("/assets/no-such.js")
    api = env.client.get("/_api/no-such")
    # 検証
    assert asset.status_code == 404
    assert asset.text != INDEX_HTML
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/problem+json")


def test_error_when_excluded_not_get(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """/_api/・/_admin/ の下の、どの入口にも該当しないパスへの GET 以外の要求は 404 を返却する（異常系）。"""
    # 準備
    env = make_server(sample_index, screen_dir=_build_dir(tmp_path, with_index=True))
    # 実行
    session_context = env.client.post("/_admin/session-context", json={"cwd": "/"})
    admin = env.client.post("/_admin/no-such", json={})
    api = env.client.put("/_api/no-such", json={})
    # 検証
    assert session_context.status_code == 404
    assert session_context.headers["content-type"].startswith("application/problem+json")
    assert admin.status_code == 404
    assert admin.headers["content-type"].startswith("application/problem+json")
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/problem+json")


def test_error_when_build_missing(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """index.html が無いとき、画面のパスは 503 でビルドを促し、画面の API は応え続ける（異常系）。"""
    # 準備
    env = make_server(sample_index, screen_dir=_build_dir(tmp_path, with_index=False))
    # 実行
    doc = env.client.get("/sample/docs/doc-1")
    api = env.client.get("/_api/sources/sample/docs")
    # 検証
    assert doc.status_code == 503
    assert doc.headers["content-type"].startswith("application/problem+json")
    assert any("ビルド" in step for step in doc.json()["nextSteps"])
    assert api.status_code == 200
