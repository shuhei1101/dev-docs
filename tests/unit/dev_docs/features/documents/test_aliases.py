from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dev_docs.integrations.project_index.types import DocumentRow, SourceView
from dev_docs.integrations.project_index.types import IndexedDocument as Document


def _alias_document(
    make_document: Callable[..., Document], doc_id: str, kind: str, path: str, **metadata: Any
) -> Document:
    """`metadata` にエイリアスのキーを持つ文書を作る。"""
    values = {"id": doc_id, **metadata}
    return make_document(id=doc_id, kind=kind, path=path, data=values, metadata=values)


def _alias_tables() -> list[DocumentRow]:
    """`alias_type: term` の行 terms・`alias_type: doc` の行 refs・`alias_type` の無い行 rules を返却する。"""
    return [
        DocumentRow(
            id="terms",
            paths=["docs/term/*.yaml"],
            schema={},
            alias_type="term",
        ),
        DocumentRow(
            id="refs",
            paths=["docs/ref/*.yaml"],
            schema={},
            alias_type="doc",
        ),
        DocumentRow(id="rules", paths=["docs/rule/*.yaml"], schema={}),
    ]


def test_alias_schema() -> None:
    """同梱したスキーマ（正常系）。"""
    from dev_docs.features.documents.aliases import alias_schema

    # 実行
    result = alias_schema()
    # 検証
    keys = result["$defs"]["alias"]["properties"]["metadata"]["properties"]
    assert {"name", "aliases", "description", "avoid", "replacement"} <= set(keys)
    assert len(result["$defs"]["alias"]["properties"]["alias_type"]["enum"]) == 9


def test_check_alias_document(make_document: Callable[..., Document]) -> None:
    """通る用語（正常系）。"""
    from dev_docs.features.documents.aliases import check_alias_document

    # 準備
    document = _alias_document(
        make_document,
        "scope",
        "terms",
        "docs/term/scope.yaml",
        alias_type="term",
        name="作業範囲",
        aliases=["scope", "担当範囲"],
        description="触ってよい範囲",
    )
    # 実行
    result = check_alias_document(document)
    # 検証
    assert result == []


def test_check_alias_document_when_aliases_number(make_document: Callable[..., Document]) -> None:
    """別名が数値（異常系）。"""
    from dev_docs.features.documents.aliases import check_alias_document

    # 準備
    document = _alias_document(
        make_document,
        "broken",
        "terms",
        "docs/term/broken.yaml",
        alias_type="term",
        name="壊れた用語",
        aliases=3,
        description="型の違う別名",
    )
    # 実行
    result = check_alias_document(document)
    # 検証
    assert [(item.path, item.rule, item.doc) for item in result] == [
        ("aliases", "文字列か文字列の並びではありません", "docs/term/broken.yaml")
    ]


def test_check_alias_document_when_required_missing(
    make_document: Callable[..., Document],
) -> None:
    """引用の種類の必須が無い（異常系）。"""
    from dev_docs.features.documents.aliases import check_alias_document

    # 準備
    command = _alias_document(
        make_document,
        "serve",
        "commands",
        "docs/command/serve.yaml",
        alias_type="command",
        name="起動",
    )
    env = _alias_document(
        make_document, "local", "envs", "docs/env/local.yaml", alias_type="env", name="手元"
    )
    # 実行
    results = [check_alias_document(command), check_alias_document(env)]
    # 検証
    assert [[(item.path, item.rule) for item in result] for result in results] == [
        [("command", "必須のキーが無い")],
        [("url", "url・port のどれか 1 つが要ります")],
    ]


def test_check_alias_document_when_aliases_string(make_document: Callable[..., Document]) -> None:
    """別名が文字列（正常系）。"""
    from dev_docs.features.documents.aliases import check_alias_document

    # 準備
    document = _alias_document(
        make_document,
        "settings",
        "refs",
        "docs/ref/settings.yaml",
        alias_type="doc",
        name="設定のリファレンス",
        aliases="settings",
        description="設定のキーの一覧",
    )
    # 実行
    result = check_alias_document(document)
    # 検証
    assert result == []


def test_collect_aliases(
    make_document: Callable[..., Document],
    make_view: Callable[..., SourceView],
) -> None:
    """用語と文書の別名と違反（正常系）。"""
    from dev_docs.features.documents.aliases import collect_aliases

    # 準備
    view = make_view(documents=_alias_tables())
    documents = [
        _alias_document(
            make_document,
            "scope",
            "terms",
            "docs/term/scope.yaml",
            alias_type="term",
            name="作業範囲",
            aliases=["scope", "担当範囲"],
            avoid=["担当領域"],
            description="触ってよい範囲",
        ),
        _alias_document(
            make_document,
            "broken",
            "terms",
            "docs/term/broken.yaml",
            alias_type="term",
            name="壊れた用語",
            aliases=3,
            description="型の違う別名",
        ),
        _alias_document(
            make_document,
            "settings",
            "refs",
            "docs/ref/settings.yaml",
            alias_type="doc",
            name="設定のリファレンス",
            aliases="settings",
            description="設定のキーの一覧",
        ),
        _alias_document(make_document, "doc-1", "rules", "docs/rule/doc-1.yaml", name="文書 1"),
    ]
    # 実行
    result = collect_aliases(view, documents)
    # 検証
    assert [(entry.id, entry.aliases, entry.avoid) for entry in result.entries] == [
        ("scope", ["scope", "担当範囲"], ["担当領域"]),
        ("settings", ["settings"], None),
    ]
    assert [item.doc for item in result.violations] == ["docs/term/broken.yaml"]
    assert result.has_alias_rows is True


def test_collect_aliases_when_no_alias_rows(
    make_document: Callable[..., Document],
    make_view: Callable[..., SourceView],
) -> None:
    """エイリアスの行が無い（正常系）。"""
    from dev_docs.features.documents.aliases import collect_aliases

    # 準備
    view = make_view(documents=_alias_tables()[2:])
    documents = [
        _alias_document(make_document, "doc-1", "rules", "docs/rule/doc-1.yaml", name="文書 1")
    ]
    # 実行
    result = collect_aliases(view, documents)
    # 検証
    assert result.entries == []
    assert result.violations == []
    assert result.has_alias_rows is False
