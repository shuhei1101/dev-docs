from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from dev_docs.features.sources.types import ScriptEntry
from dev_docs.features.view.page import render_doc_view, render_error_page
from dev_docs.features.view.types import ScreenPath
from dev_docs.shared.errors import DocumentNotFoundError, UnknownSourceError


class FakeTemplates:
    """描いたテンプレートの名前と値を記録する画面のテンプレートの偽物。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def TemplateResponse(self, request: Any, name: str, context: dict[str, Any]) -> HTMLResponse:
        self.calls.append((name, context))
        return HTMLResponse("not found", status_code=404)


def _html(response: HTMLResponse) -> str:
    """HTML の応答の本文を文字列で返す。"""
    return bytes(response.body).decode("utf-8")


def test_render_doc_view(
    make_view_env: Callable[..., SimpleNamespace], make_request: Callable[..., Request]
) -> None:
    """配信元のトップ（正常系）。"""
    # 準備
    env = make_view_env()
    # 実行
    response = render_doc_view(
        make_request("/sample/"),
        ScreenPath("sample", None, ""),
        handlers=env.handlers,
        diff_ref=None,
    )
    # 検証
    html = _html(response)
    assert response.status_code == 200
    assert "data-mdmark-source" in html
    assert "# A" in html


def test_render_doc_view_when_diff(
    git_repo: Callable[..., Path],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    make_view_env: Callable[..., SimpleNamespace],
    make_request: Callable[..., Request],
    read_page_state: Callable[[str], dict[str, Any]],
) -> None:
    """差分の元（正常系）。"""
    # 準備
    root = git_repo({"docs/a.yaml": "id: a\nname: A\n"})
    previous = run_git(root, "rev-parse", "HEAD").strip()
    commit_all(root, {"docs/a.yaml": "id: a\nname: A2\n"})
    env = make_view_env(root=root, is_git=True, repo_root=root)
    # 実行
    response = render_doc_view(
        make_request("/sample/docs/a"),
        ScreenPath("sample", None, "docs/a"),
        handlers=env.handlers,
        diff_ref="HEAD~1",
    )
    # 検証
    html = _html(response)
    assert "data-mdmark-diff-source" in html
    assert "# A\n" in html
    assert previous.startswith(read_page_state(html)["diff"]["commit"])


def test_render_doc_view_when_convert_failed(
    make_view_env: Callable[..., SimpleNamespace], make_request: Callable[..., Request]
) -> None:
    """変換の失敗（正常系）。"""
    # 準備
    run = ["python3", "-c", "import time; time.sleep(5)"]
    env = make_view_env(converters=[ScriptEntry(id="c", run=run)], converter_timeout=1)
    # 実行
    response = render_doc_view(
        make_request("/sample/docs/a"),
        ScreenPath("sample", None, "docs/a"),
        handlers=env.handlers,
        diff_ref=None,
    )
    # 検証
    html = _html(response)
    assert response.status_code == 200
    assert "変換の失敗" in html
    assert "timeout" in html


def test_render_doc_view_when_missing(
    make_view_env: Callable[..., SimpleNamespace], make_request: Callable[..., Request]
) -> None:
    """無い文書（異常系）。"""
    # 準備
    env = make_view_env()
    # 実行・検証
    with pytest.raises(DocumentNotFoundError):
        render_doc_view(
            make_request("/sample/docs/none"),
            ScreenPath("sample", None, "docs/none"),
            handlers=env.handlers,
            diff_ref=None,
        )


def test_render_error_page(
    make_view_env: Callable[..., SimpleNamespace],
    make_handlers: Callable[..., Any],
    make_request: Callable[..., Request],
) -> None:
    """無い配信元（正常系）。"""
    # 準備
    env = make_view_env()
    templates = FakeTemplates()
    handlers = make_handlers(
        registry=env.handlers.registry, templates=templates, columns=env.handlers.columns
    )
    error = UnknownSourceError(message="配信元 none はありません", source_id="none")
    # 実行
    response = render_error_page(make_request("/none/"), error, handlers=handlers)
    # 検証
    name, context = templates.calls[0]
    assert response.status_code == 404
    assert name == "not_found.html"
    assert context["missing_rows"] == [{"label": "配信元", "value": "`none` は配信していません。"}]
    assert ("sample", "/sample/") in context["links"]
    assert "/_settings/" in [url for _, url in context["links"]]
