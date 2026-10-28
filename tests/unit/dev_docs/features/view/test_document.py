from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from dev_docs.features.sources.types import DocumentTable, ScriptEntry
from dev_docs.features.view.document import get_document, not_found_fields
from dev_docs.shared.errors import DocumentNotFoundError, RefNotFoundError


def test_get_document(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """配信元のトップ（正常系）。"""
    # 準備
    tables = [
        DocumentTable(id="rules", type="yaml", paths=["docs/*.yaml"]),
        DocumentTable(id="notes", type="markdown", paths=["notes/*.md"]),
    ]
    nav = {
        "tabs": [
            {"title": "規約", "items": [{"auto": {"document": "rules"}}]},
            {"title": "メモ", "items": [{"auto": {"document": "notes"}}]},
        ]
    }
    env = make_view_env(
        {"docs/a.yaml": "id: a\nname: A\n", "notes/x.md": "# X\n"}, tables=tables, nav=nav
    )
    # 実行
    response = get_document("sample", None, handlers=env.handlers, ref=None, diff_ref=None)
    # 検証
    assert response.path == "docs/a"
    assert response.markdown is not None
    assert "# A" in response.markdown
    assert [tab.title for tab in response.tabs] == ["規約", "メモ"]
    assert [tab.active for tab in response.tabs] == [True, False]


def test_get_document_when_diff(
    git_repo: Callable[..., Path],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    make_view_env: Callable[..., SimpleNamespace],
) -> None:
    """変わった項目（正常系）。"""
    # 準備
    root = git_repo({"docs/a.yaml": "id: a\nname: A\n"})
    previous = run_git(root, "rev-parse", "HEAD").strip()
    current = commit_all(root, {"docs/a.yaml": "id: a\nname: A2\n"})
    env = make_view_env(root=root, is_git=True, repo_root=root)
    # 実行
    response = get_document(
        "sample", "docs/a", handlers=env.handlers, ref=current, diff_ref=previous
    )
    # 検証
    assert response.changed_items == ["name"]


def test_get_document_when_convert_failed(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """変換の失敗（正常系）。"""
    # 準備
    run = ["python3", "-c", "import time; time.sleep(5)"]
    env = make_view_env(converters=[ScriptEntry(id="c", run=run)], converter_timeout=1)
    # 実行
    response = get_document("sample", "docs/a", handlers=env.handlers, ref=None, diff_ref=None)
    # 検証
    assert response.markdown is None
    assert response.conversion_error is not None
    assert response.conversion_error.reason == "timeout"


def test_get_document_when_yaml_unreadable(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """YAML を読めない（正常系）。"""
    # 準備
    env = make_view_env({"docs/a.yaml": "a: [1\n"})
    # 実行
    response = get_document("sample", "docs/a", handlers=env.handlers, ref=None, diff_ref=None)
    # 検証
    error = response.conversion_error
    assert response.markdown is None
    assert error is not None
    assert error.reason == "invalid_yaml"
    assert error.kind == "rules"
    assert error.file == "docs/a.yaml"
    assert error.line is not None
    assert error.line >= 1
    assert error.column is not None
    assert error.column >= 1


def test_get_document_when_missing(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """無い文書（異常系）。"""
    # 準備
    env = make_view_env()
    # 実行・検証
    with pytest.raises(DocumentNotFoundError, match="docs/none"):
        get_document("sample", "docs/none", handlers=env.handlers, ref=None, diff_ref=None)


def test_not_found_fields() -> None:
    """例外ごとの値（正常系）。"""
    # 準備
    ref_error = RefNotFoundError(
        message="ref を解決できません: no-such-branch", argument="ref", value="no-such-branch"
    )
    doc_error = DocumentNotFoundError(
        message="文書がありません: no-such-doc", missing=["no-such-doc"]
    )
    # 実行
    ref_fields = not_found_fields(ref_error, None)
    doc_fields = not_found_fields(doc_error, "no-such-doc")
    # 検証
    assert ref_fields == {"missing": "ref", "value": "no-such-branch"}
    assert doc_fields == {"missing": "doc", "value": "no-such-doc"}
