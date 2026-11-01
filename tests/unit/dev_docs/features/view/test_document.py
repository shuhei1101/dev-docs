from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from dev_docs.features.sources.types import DocumentTable, ScriptEntry
from dev_docs.features.view.document import get_document, not_found_fields
from dev_docs.features.view.types import NavItem
from dev_docs.shared.errors import DocumentNotFoundError, RefNotFoundError


def test_get_document(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """配信元のトップ（正常系）。"""
    # 準備
    tables = [
        DocumentTable(id="rules", paths=["docs/*.yaml"], schema_path="schemas/rule.schema.yaml"),
        DocumentTable(
            id="notes",
            paths=["notes/files.yaml"],
            schema_path="schemas/rule.schema.yaml",
            records="files",
            body_file="path",
        ),
    ]
    nav = {
        "tabs": [
            {"title": "規約", "items": [{"auto": {"document": "rules"}}]},
            {"title": "メモ", "items": [{"auto": {"document": "notes"}}]},
        ]
    }
    env = make_view_env(
        {
            "docs/a.yaml": "id: a\nname: A\n",
            "notes/files.yaml": "files:\n  - path: x.md\n",
            "notes/x.md": "# X\n",
        },
        tables=tables,
        nav=nav,
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
    """差分の結果とサイドバーの変化（正常系）。"""
    # 準備
    root = git_repo(
        {
            "docs/a.yaml": "id: a\nname: A\n",
            "docs/b.yaml": "id: b\nname: B\n",
            "docs/c.yaml": "id: c\nname: C\n",
        }
    )
    previous = run_git(root, "rev-parse", "HEAD").strip()
    run_git(root, "rm", "-q", "docs/c.yaml")
    current = commit_all(
        root, {"docs/a.yaml": "id: a\nname: A2\n", "docs/d.yaml": "id: d\nname: D\n"}
    )
    env = make_view_env(root=root, is_git=True, repo_root=root)
    # 実行
    response = get_document(
        "sample", "docs/a", handlers=env.handlers, ref=current, diff_ref=previous
    )
    # 検証
    assert response.diff is not None
    assert response.diff.base == previous
    assert response.diff.change == "modified"
    assert response.diff.changed_items == ["name"]
    changes = {item.path: item.change for tab in response.tabs for item in _pages(tab.items)}
    assert changes["docs/a"] == "modified"
    assert changes["docs/d"] == "added"
    assert changes["docs/c"] == "deleted"


def _pages(items: list[NavItem]) -> list[NavItem]:
    """入れ子の項目から page だけを平らに集める。"""
    pages: list[NavItem] = []
    for item in items:
        if item.kind == "page":
            pages.append(item)
        pages.extend(_pages(item.items))
    return pages


def test_get_document_when_not_git(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """Git 管理外の更新日時と差分（正常系）。"""
    # 準備
    env = make_view_env()
    file = env.root / "docs" / "a.yaml"
    # 実行
    response = get_document("sample", "docs/a", handlers=env.handlers, ref=None, diff_ref="main")
    # 検証
    assert response.updated_at == datetime.fromtimestamp(file.stat().st_mtime, tz=UTC)
    assert response.diff is None
    assert response.ref is None


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


def test_get_document_when_body_path(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """管理用の YAML の行の文書の本文のファイルのパス（正常系）。"""
    # 準備
    tables = [
        DocumentTable(id="rules", paths=["docs/*.yaml"], schema_path="schemas/rule.schema.yaml"),
        DocumentTable(
            id="notes",
            paths=["notes/files.yaml"],
            schema_path="schemas/rule.schema.yaml",
            records="files",
            body_file="path",
        ),
    ]
    env = make_view_env(
        {
            "docs/a.yaml": "id: a\nname: A\n",
            "notes/files.yaml": "files:\n  - path: b.md\n",
            "notes/b.md": "# B\n",
        },
        tables=tables,
    )
    # 実行
    by_page = get_document(
        "sample", "notes/files/notes/b.md", handlers=env.handlers, ref=None, diff_ref=None
    )
    by_body_path = get_document(
        "sample", "notes/b.md", handlers=env.handlers, ref=None, diff_ref=None
    )
    plain = get_document("sample", "docs/a", handlers=env.handlers, ref=None, diff_ref=None)
    # 検証
    assert by_page.body_path == "notes/b.md"
    assert by_page.path == "notes/files/notes/b.md"
    assert by_body_path.body_path == "notes/b.md"
    assert by_body_path.path == "notes/files/notes/b.md"
    assert plain.body_path is None


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


def test_get_document_when_aliases(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """エイリアスを返す（正常系）。"""
    # 準備
    tables = [
        DocumentTable(
            id="terms",
            paths=["docs/term/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
            alias_type="term",
        ),
        DocumentTable(
            id="refs",
            paths=["docs/ref/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
            alias_type="doc",
        ),
    ]
    env = make_view_env(
        {
            "docs/term/scope.yaml": (
                "id: scope\n"
                "name: 作業範囲\n"
                "description: 触ってよい範囲\n"
                "aliases: [scope, 担当範囲]\n"
                "avoid: [担当領域]\n"
            ),
            "docs/ref/settings.yaml": (
                "id: settings\nname: 設定のリファレンス\ndescription: 設定のキーの一覧\n"
                "aliases: [settings]\n"
            ),
        },
        tables=tables,
    )
    # 実行
    response = get_document(
        "sample", "docs/term/scope", handlers=env.handlers, ref=None, diff_ref=None
    )
    # 検証
    aliases = response.model_dump(mode="json")["aliases"]
    assert [item["id"] for item in aliases] == ["scope", "settings"]
    assert aliases[0]["avoid"] == ["担当領域"]
    assert "avoid" not in aliases[1]
