from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest

from dev_docs.features.view.document import get_document, not_found_fields
from dev_docs.features.view.types import DocumentResponse, NavItem
from dev_docs.shared.errors import (
    DocumentNotFoundError,
    ProjectIndexUnreachableError,
    RefNotFoundError,
)

from ...conftest import RULE_SCHEMA, FakeIndex, config_json, doc_json

UPDATED = "2026-11-01T10:00:00+09:00"
LIST_VALUE = {"items": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]}


def _row(row_id: str, paths: list[str], **extra: Any) -> dict[str, Any]:
    """配信元の表示の設定の文書の行の JSON を作る。"""
    return {"id": row_id, "paths": paths, "schema": RULE_SCHEMA, **extra}


def _serve(fake_index: FakeIndex, docs: list[dict[str, Any]], **config: Any) -> None:
    """偽物の project-index に配信元 sample と既定のリビジョンの文書を配置する。"""
    fake_index.configs["sample"] = config_json("sample", **config)
    fake_index.docs["sample"] = {None: docs}


def _get(
    handlers: Any, path: str | None, *, ref: str | None = None, diff_ref: str | None = None
) -> DocumentResponse:
    """文書の取得を実行する。"""
    return asyncio.run(get_document("sample", path, handlers=handlers, ref=ref, diff_ref=diff_ref))


def _pages(items: list[NavItem]) -> list[NavItem]:
    """入れ子の項目から page だけを平らに集める。"""
    pages: list[NavItem] = []
    for item in items:
        if item.kind == "page":
            pages.append(item)
        pages.extend(_pages(item.items))
    return pages


def test_get_document(fake_index: FakeIndex, make_handlers: Callable[..., Any]) -> None:
    """配信元のトップ（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {"title": "規約", "items": [{"auto": {"document": "rules"}}]},
            {"title": "メモ", "items": [{"auto": {"document": "notes"}}]},
        ]
    }
    documents = [
        doc_json("a", "docs/a.yaml", name="A"),
        doc_json("n-1", "notes/files.yaml", kind="notes", record_index=0, name="N"),
    ]
    _serve(
        fake_index,
        documents,
        nav=nav,
        documents=[
            _row("rules", ["docs/*.yaml"]),
            _row("notes", ["notes/files.yaml"], records="files"),
        ],
    )
    # 実行
    response = _get(make_handlers(), None)
    # 検証
    assert response.path == "docs/a"
    assert response.markdown is not None
    assert "# A" in response.markdown
    assert [tab.title for tab in response.tabs] == ["規約", "メモ"]
    assert [tab.active for tab in response.tabs] == [True, False]


def test_get_document_when_diff(fake_index: FakeIndex, make_handlers: Callable[..., Any]) -> None:
    """差分の結果とサイドバーの変化（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json("sample")
    fake_index.docs["sample"] = {
        "current": [
            doc_json("a", "docs/a.yaml", name="A2", version="v-a2"),
            doc_json("b", "docs/b.yaml", name="B"),
            doc_json("d", "docs/d.yaml", name="D"),
        ],
        "previous": [
            doc_json("a", "docs/a.yaml", name="A", version="v-a1"),
            doc_json("b", "docs/b.yaml", name="B"),
            doc_json("c", "docs/c.yaml", name="C"),
        ],
    }
    # 実行
    response = _get(make_handlers(), "docs/a", ref="current", diff_ref="previous")
    # 検証
    assert response.diff is not None
    assert response.diff.base == "previous"
    assert response.diff.change == "modified"
    assert response.diff.changed_items == ["name"]
    changes = {item.path: item.change for tab in response.tabs for item in _pages(tab.items)}
    assert changes["docs/a"] == "modified"
    assert changes["docs/d"] == "added"
    assert changes["docs/c"] == "deleted"


def test_get_document_when_convert_failed(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index の変換の失敗（正常系）。"""
    # 準備
    _serve(fake_index, [doc_json("a", "docs/a.yaml")])
    fake_index.details[("sample", "docs/a.yaml")] = {
        "failure": {"reason": "timeout", "kind": "rules", "detail": "45 秒", "script": "conv"}
    }
    # 実行
    response = _get(make_handlers(), "docs/a")
    # 検証
    assert response.markdown is None
    assert response.conversion_error is not None
    assert response.conversion_error.reason == "timeout"


def test_get_document_when_yaml_unreadable(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """YAML を読み込めない（正常系）。"""
    # 準備
    _serve(fake_index, [doc_json("b", "docs/b.yaml")])
    fake_index.unreadable["sample"] = [
        {
            "reason": "invalid_yaml",
            "kind": "rules",
            "detail": "閉じていない",
            "file": "docs/a.yaml",
            "line": 1,
            "column": 4,
        }
    ]
    # 実行
    response = _get(make_handlers(), "docs/a")
    # 検証
    error = response.conversion_error
    paths = [request.url.path for request in fake_index.requests]
    assert "/sources/sample/docs/docs/a" in paths
    assert response.markdown is None
    assert error is not None
    assert (error.reason, error.file, error.line, error.column) == (
        "invalid_yaml",
        "docs/a.yaml",
        1,
        4,
    )


def test_get_document_when_missing(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """無い文書（異常系）。"""
    # 準備
    _serve(fake_index, [doc_json("a", "docs/a.yaml")])
    # 実行・検証
    with pytest.raises(DocumentNotFoundError, match="docs/none"):
        _get(make_handlers(), "docs/none")


def test_get_document_when_not_git(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """Git 管理外の更新日時と差分（正常系）。"""
    # 準備
    _serve(fake_index, [doc_json("a", "docs/a.yaml", updated=UPDATED)], git=False)
    # 実行
    response = _get(make_handlers(), "docs/a", diff_ref="main")
    # 検証
    assert response.updated_at == datetime.fromisoformat(UPDATED)
    assert response.diff is None
    assert response.ref is None


def test_get_document_when_aliases(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """エイリアスを返却する（正常系）。"""
    # 準備
    scope = {
        "id": "scope",
        "name": "作業範囲",
        "description": "触ってよい範囲",
        "aliases": ["scope", "担当範囲"],
        "avoid": ["担当領域"],
        "alias_type": "term",
    }
    settings = {
        "id": "settings",
        "name": "設定のリファレンス",
        "description": "設定のキーの一覧",
        "aliases": ["settings"],
        "alias_type": "doc",
    }
    _serve(
        fake_index,
        [
            doc_json("scope", "docs/term/scope.yaml", kind="terms", data=scope, metadata=scope),
            doc_json(
                "settings", "docs/ref/settings.yaml", kind="refs", data=settings, metadata=settings
            ),
        ],
        documents=[
            _row("terms", ["docs/term/*.yaml"], aliasType="term"),
            _row("refs", ["docs/ref/*.yaml"], aliasType="doc"),
        ],
    )
    # 実行
    response = _get(make_handlers(), "docs/term/scope")
    # 検証
    aliases = response.model_dump(mode="json")["aliases"]
    assert [item["id"] for item in aliases] == ["scope", "settings"]
    assert aliases[0]["avoid"] == ["担当領域"]
    assert "avoid" not in aliases[1]


def test_get_document_when_decision(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """検討事項の文書を返却する（正常系）。"""
    # 準備
    _serve(fake_index, [doc_json("a", "docs/a.yaml")], decisions=["tmp/a", "tmp/b"])
    fake_index.decision_texts[("sample", "D-1")] = "# D-1 の本文\n"
    # 実行
    response = _get(make_handlers(), "_decisions/D-1")
    # 検証
    assert response.markdown == "# D-1 の本文\n"
    assert response.path == "_decisions/D-1"
    assert response.diff is None
    assert response.body_path is None
    assert [tab.active for tab in response.tabs] == [False]


def test_get_document_when_decision_ambiguous(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index が検討事項の文書を返却しない（異常系）。"""
    # 準備
    _serve(fake_index, [doc_json("a", "docs/a.yaml")], decisions=["tmp/a", "tmp/b"])
    # 実行・検証
    with pytest.raises(DocumentNotFoundError):
        _get(make_handlers(), "_decisions/D-2")


def test_get_document_when_body_path(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """管理用の YAML の行の文書の本文のファイルのパス（正常系）。"""
    # 準備
    _serve(
        fake_index,
        [
            doc_json("a", "docs/a.yaml", name="A"),
            doc_json(
                "notes/b.md",
                "notes/files.yaml",
                kind="notes",
                record_index=0,
                body_path="notes/b.md",
                body="# B\n",
                data={"path": "b.md"},
            ),
        ],
        documents=[
            _row("rules", ["docs/*.yaml"]),
            _row("notes", ["notes/files.yaml"], records="files"),
        ],
    )
    handlers = make_handlers()
    # 実行
    by_page = _get(handlers, "notes/files/notes/b.md")
    by_body_path = _get(handlers, "notes/b.md")
    plain = _get(handlers, "docs/a")
    # 検証
    assert (by_page.body_path, by_page.path) == ("notes/b.md", "notes/files/notes/b.md")
    assert (by_body_path.body_path, by_body_path.path) == ("notes/b.md", "notes/files/notes/b.md")
    assert plain.body_path is None


def test_get_document_when_embed(fake_index: FakeIndex, make_handlers: Callable[..., Any]) -> None:
    """埋め込みの値を project-index から取る（正常系）。"""
    # 準備
    _serve(
        fake_index,
        [
            doc_json(
                "m",
                "docs/m.yaml",
                body_path="docs/m.md",
                body="# M\n\n<!-- embed: data/list.yaml#items -->\n",
            )
        ],
    )
    fake_index.details[("sample", "data/list.yaml")] = {
        "document": doc_json("list", "data/list.yaml", data=LIST_VALUE)
    }
    # 実行
    response = _get(make_handlers(), "docs/m.md")
    # 検証
    assert response.markdown is not None
    assert "| a | A |" in response.markdown
    assert "| b | B |" in response.markdown
    assert "embed:data/list.yaml#items" in response.table_keys


def test_get_document_when_unreachable(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    fake_index.refused = True
    # 実行・検証
    with pytest.raises(ProjectIndexUnreachableError):
        _get(make_handlers(), "docs/a")


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
