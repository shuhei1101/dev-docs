from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from dev_docs.features.convert.service import ConvertService
from dev_docs.features.view.edit import (
    WHOLE_FILE_PATH,
    PreviewNotYamlError,
    PreviewRequest,
    body_item_paths,
    build_document_edit,
    collect_blocks,
    dump_source,
    preview_document,
)
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.integrations.project_index.types import (
    DocumentDetail,
    DocumentRow,
    IndexedDocument,
    IndexFailure,
    SourceView,
)
from dev_docs.shared.errors import DocumentNotFoundError
from dev_docs.shared.yaml_io import load_yaml

from ...conftest import FakeIndex, config_json, doc_json

BASE_COMMIT = "0a1b2c3d4e5f60718293a4b5c6d7e8f901234567"
NOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "title": "ID", "x-hidden": True},
        "title": {"type": "string", "title": "タイトル"},
        "status": {"type": "string", "title": "状態", "enum": ["draft", "current"]},
        "summary": {"type": "string", "title": "概要"},
        "items": {
            "type": "array",
            "title": "項目",
            "x-heading": "項目",
            "x-shape": "sections",
            "x-key": "id",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "title": "ID", "x-hidden": True},
                    "body": {
                        "type": "string",
                        "title": "本文",
                        "contentMediaType": "text/markdown",
                    },
                },
            },
        },
        "rows": {
            "type": "array",
            "title": "置き換え",
            "x-shape": "table",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "title": "語"},
                    "replacement": {"type": "string", "title": "置き換え先"},
                },
            },
        },
    },
}
N1_VALUE: dict[str, Any] = {
    "id": "n1",
    "title": "n1",
    "status": "draft",
    "summary": "概要",
    "items": [{"id": "i1", "body": "**本文**"}],
    "rows": [{"word": "a", "replacement": "b"}, {"word": "c", "replacement": "d"}],
}
N1_RANGES = [
    ("title", "# n1"),
    ("status", "**状態**: draft"),
    ("summary", "**概要**: 概要"),
    ("#items[i1].body", "**本文**"),
    ("rows", "| 語 | 置き換え先 |"),
]


def _note_view(**row: Any) -> SourceView:
    """種類 note の行だけを持つ配信元の表示の設定を作る。"""
    return SourceView(
        id="sample",
        git=True,
        default_ref="develop",
        documents=[DocumentRow(id="note", paths=["notes/*.yaml"], schema=NOTE_SCHEMA, **row)],
    )


def _n1(make_document: Callable[..., IndexedDocument]) -> IndexedDocument:
    """種類 note の文書 n1 を作る。"""
    return make_document(
        id="n1",
        kind="note",
        path="notes/n1.yaml",
        data=N1_VALUE,
        metadata={"id": "n1", "name": "n1"},
    )


def _config(**extra: Any) -> dict[str, Any]:
    """配信元の設定の取得の `value`（種類 note・files・log の行）を作る。"""
    return {
        "documents": [
            {"id": "note", "paths": ["notes/*.yaml"]},
            {"id": "files", "paths": ["docs/files.yml"], "records": "files"},
            {"id": "log", "paths": [], "sqlite": {"path": "log.db", "table": "log"}},
        ],
        **extra,
    }


def _build(view: SourceView, detail: DocumentDetail, **overrides: Any) -> Any:
    """本文の編集の情報の組み立てを既定の引数で呼ぶ。"""
    values: dict[str, Any] = {
        "write_api_kinds": ["note", "files", "log"],
        "base_commit": BASE_COMMIT,
        "version": "v-n1",
        "item_ranges": N1_RANGES,
    }
    values.update(overrides)
    config = values.pop("config", _config())
    return build_document_edit(view, config, detail, **values)


def test_build_document_edit(make_document: Callable[..., IndexedDocument]) -> None:
    """YAML の文書（正常系）。"""
    # 準備
    detail = DocumentDetail(document=_n1(make_document))
    # 実行
    edit = _build(_note_view(), detail)
    # 検証
    assert edit is not None
    assert edit.language == "yaml"
    assert [block.path for block in edit.blocks] == [
        "status",
        "summary",
        "#items[i1].body",
        "rows",
    ]
    assert [block.type for block in edit.blocks] == ["enum", "string", "markdown", "table"]
    assert edit.title_block is not None
    assert edit.title_block.path == "title"
    assert (edit.doc_id, edit.kind, edit.file_path) == ("n1", "note", "notes/n1.yaml")
    assert (edit.version, edit.base_commit) == ("v-n1", BASE_COMMIT)


def test_build_document_edit_when_markdown(make_document: Callable[..., IndexedDocument]) -> None:
    """Markdown の本文（正常系）。"""
    # 準備
    view = SourceView(
        id="sample",
        git=True,
        default_ref="develop",
        documents=[DocumentRow(id="files", paths=["docs/files.yml"], schema={}, records="files")],
    )
    document = make_document(
        id="guide",
        kind="files",
        path="docs/files.yml",
        data={"path": "guide.md", "summary": "ガイド"},
        body="# ガイド\n\n本文\n",
        body_path="guide.md",
    )
    # 実行
    edit = _build(view, DocumentDetail(document=document), item_ranges=[])
    # 検証
    assert edit is not None
    assert edit.language == "markdown"
    assert edit.source == "# ガイド\n\n本文\n"
    assert edit.blocks == []
    assert edit.title_block is None
    assert edit.file_path == "guide.md"


@pytest.mark.parametrize(
    ("kind", "body_path", "config"),
    [
        pytest.param("memo", None, _config(), id="not-write-api-kind"),
        pytest.param("log", None, _config(), id="sqlite"),
        pytest.param(
            "files",
            "guide.md",
            _config(directCommit={"metadataOnlyKinds": ["files"]}),
            id="metadata-only",
        ),
        pytest.param("files", "tool.py", _config(), id="not-markdown-body"),
    ],
)
def test_build_document_edit_when_not_editable(
    make_document: Callable[..., IndexedDocument],
    kind: str,
    body_path: str | None,
    config: dict[str, Any],
) -> None:
    """編集できない文書（正常系）。"""
    # 準備
    document = make_document(id="d1", kind=kind, path="docs/d1.yaml", body_path=body_path)
    # 実行
    edit = _build(_note_view(), DocumentDetail(document=document), config=config)
    # 検証
    assert edit is None


def test_build_document_edit_when_converter(make_document: Callable[..., IndexedDocument]) -> None:
    """変換のスクリプトを指す種類（正常系）。"""
    # 準備
    detail = DocumentDetail(document=_n1(make_document), markdown="# 変換した\n")
    # 実行
    edit = _build(_note_view(converter="python conv.py"), detail)
    # 検証
    assert edit is not None
    assert edit.language == "yaml"
    assert edit.blocks == []
    assert edit.title_block is None


def test_build_document_edit_when_failure(make_document: Callable[..., IndexedDocument]) -> None:
    """変換に失敗した文書は編集の情報を返却しない（正常系）。"""
    # 準備
    detail = DocumentDetail(
        document=_n1(make_document),
        failure=IndexFailure(reason="timeout", kind="note", detail="制限時間を超えました"),
    )
    # 実行
    edit = _build(_note_view(), detail)
    # 検証
    assert edit is None


def test_dump_source() -> None:
    """キーの順と複数行（正常系）。"""
    # 準備
    value = {"title": "A", "items": [{"id": "i1", "body": "1 行目\n2 行目\n"}], "summary": "B"}
    # 実行
    text = dump_source(value)
    # 検証
    assert [line.split(":")[0] for line in text.splitlines() if not line.startswith(" ")] == [
        "title",
        "items",
        "summary",
    ]
    assert "body: |" in text
    assert load_yaml(text) == value


def test_collect_blocks() -> None:
    """型ごとの部品の種類（正常系）。"""
    # 準備
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "title": "状態", "enum": ["draft", "current"]},
            "body": {"type": "string", "title": "本文", "contentMediaType": "text/markdown"},
            "summary": {"type": "string", "title": "概要"},
            "rows": {
                "type": "array",
                "title": "置き換え",
                "items": {
                    "type": "object",
                    "properties": {"word": {"type": "string"}, "replacement": {"type": "string"}},
                },
            },
            "order": {"type": "integer", "title": "順番"},
        },
    }
    value = {
        "status": "draft",
        "body": "**本文**",
        "summary": "概要",
        "rows": [{"word": "a"}],
        "order": 3,
    }
    # 実行
    blocks, title = collect_blocks(value, schema, None)
    # 検証
    assert [(block.path, block.type) for block in blocks] == [
        ("status", "enum"),
        ("body", "markdown"),
        ("summary", "string"),
        ("rows", "table"),
    ]
    assert blocks[0].options == ["draft", "current"]
    assert blocks[3].columns == ["word", "replacement"]
    assert blocks[3].value == [{"word": "a", "replacement": ""}]
    assert title is None


def test_collect_blocks_when_keyed_array() -> None:
    """x-key を持つ配列の要素の中の項目（正常系）。"""
    # 準備
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "title": "項目",
                "x-key": "id",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "title": "ID"},
                        "body": {"type": "string", "title": "本文"},
                        "order": {"type": "integer", "title": "順番"},
                    },
                },
            }
        },
    }
    value = {
        "items": [{"id": "i1", "body": "1", "order": 1}, {"id": "i2", "body": "2", "order": 2}]
    }
    # 実行
    blocks, _ = collect_blocks(value, schema, None)
    # 検証
    assert [block.path for block in blocks] == [
        "#items[i1].id",
        "#items[i1].body",
        "#items[i2].id",
        "#items[i2].body",
    ]
    assert blocks[1].label == "i1 の 本文"


def test_collect_blocks_when_sections() -> None:
    """セクションで描く x-key の配列（正常系）。"""
    # 準備
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "title": "項目",
                "x-key": "id",
                "x-shape": "sections",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "title": "ID"},
                        "body": {"type": "string", "title": "本文"},
                    },
                },
            }
        },
    }
    value = {"items": [{"id": "i1", "body": "1"}, {"id": "i2", "body": "2"}]}
    # 実行
    blocks, _ = collect_blocks(value, schema, None)
    # 検証
    assert all(block.type != "table" for block in blocks)
    assert [block.path for block in blocks] == [
        "#items[i1].id",
        "#items[i1].body",
        "#items[i2].id",
        "#items[i2].body",
    ]


def test_collect_blocks_when_hidden() -> None:
    """除く項目（正常系）。"""
    # 準備
    schema = {
        "type": "object",
        "properties": {
            "secret": {"type": "string", "title": "内部", "x-hidden": True},
            "nodes": {
                "type": "array",
                "title": "図",
                "x-shape": "diagram",
                "items": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
            "meta": {"type": "object", "title": "入れ子", "properties": {"a": {"type": "string"}}},
            "steps": {
                "type": "array",
                "title": "手順",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "detail": {"type": "object", "properties": {}},
                    },
                },
            },
        },
    }
    value = {
        "secret": "s",
        "nodes": [{"id": "n"}],
        "meta": {"a": "b"},
        "steps": [{"name": "s1", "detail": {}}],
    }
    # 実行
    blocks, _ = collect_blocks(value, schema, None)
    # 検証
    assert blocks == []


def test_collect_blocks_when_ranges_missing() -> None:
    """描いていない項目（正常系）。"""
    # 準備
    ranges = [("title", "# n1"), ("#items[i1].body", "**本文**"), ("status", "**状態**: draft")]
    # 実行
    blocks, title = collect_blocks(N1_VALUE, NOTE_SCHEMA, ranges)
    # 検証
    assert [block.path for block in blocks] == ["#items[i1].body", "status"]
    assert [block.markdown for block in blocks] == ["**本文**", "**状態**: draft"]
    assert title is not None
    assert title.markdown == "# n1"


def _serve_note(fake_index: FakeIndex, docs: list[dict[str, Any]], **config: Any) -> None:
    """配信元 sample に種類の行と、既定のブランチと編集を始めたときのコミットの文書を配置する。"""
    cfg = config_json(
        "sample",
        documents=[
            {"id": "note", "paths": ["notes/*.yaml"], "schema": NOTE_SCHEMA},
            {"id": "files", "paths": ["docs/files.yml"], "records": "files", "schema": {}},
            {"id": "memo", "paths": ["memo/*.yaml"], "schema": {}},
        ],
    )
    cfg.update(config)
    fake_index.configs["sample"] = cfg
    fake_index.docs["sample"] = {None: docs, BASE_COMMIT: docs}
    fake_index.settings = {
        "settingsPath": "/pi/settings.yaml",
        "sources": [
            {
                "id": "sample",
                "config": ["/repo/project-index.yaml"],
                "enabled": True,
                "scope": {"read": [], "write": None},
                "outsideRead": True,
                "status": "serving",
                "errors": [],
                "configVersion": None,
                "directCommit": {"writeApiKinds": ["note", "files"]},
            }
        ],
    }


def _paths(
    make_client: Callable[..., ProjectIndexClient], doc_path: str, doc_id: str
) -> frozenset[str]:
    """修正できる項目のパスの取得を実行する。"""
    return asyncio.run(
        body_item_paths(
            make_client(),
            "sample",
            doc_path,
            doc_id,
            base_commit=BASE_COMMIT,
            convert=ConvertService(),
        )
    )


def test_body_item_paths(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """YAML の文書の項目のパス（正常系）。"""
    # 準備
    _serve_note(fake_index, [doc_json("n1", "notes/n1.yaml", kind="note", data=N1_VALUE)])
    # 実行
    paths = _paths(make_client, "notes/n1.yaml", "n1")
    # 検証
    assert {"summary", "#items[i1].body", "title", WHOLE_FILE_PATH} <= paths
    detail = next(item for item in fake_index.requests if item.url.path.endswith("n1.yaml"))
    assert detail.url.params.get("ref") == BASE_COMMIT


def test_body_item_paths_when_markdown(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """Markdown の文書（正常系）。"""
    # 準備
    guide = doc_json(
        "guide",
        "docs/files.yml",
        kind="files",
        data={"path": "guide.md"},
        body_path="guide.md",
        body="# ガイド\n",
    )
    _serve_note(fake_index, [guide])
    # 実行
    paths = _paths(make_client, "guide.md", "guide")
    # 検証
    assert paths == frozenset({WHOLE_FILE_PATH})


@pytest.mark.parametrize(
    ("document", "config"),
    [
        pytest.param(
            doc_json("tool", "docs/files.yml", kind="files", body_path="tool.py", body="x = 1\n"),
            {},
            id="not-markdown-body",
        ),
        pytest.param(
            doc_json("guide", "docs/files.yml", kind="files", body_path="guide.md", body="# G\n"),
            {"directCommit": {"metadataOnlyKinds": ["files"]}},
            id="metadata-only",
        ),
        pytest.param(
            doc_json("m1", "memo/m1.yaml", kind="memo", data={"id": "m1", "name": "M"}),
            {},
            id="not-write-api-kind",
        ),
    ],
)
def test_body_item_paths_when_not_editable(
    fake_index: FakeIndex,
    make_client: Callable[..., ProjectIndexClient],
    document: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """本文を編集できない文書（正常系）。"""
    # 準備
    _serve_note(fake_index, [document], **config)
    # 実行
    paths = _paths(make_client, document["bodyPath"] or document["path"], document["id"])
    # 検証
    assert paths == frozenset()


def test_body_item_paths_when_not_rendered(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """描いていない項目（正常系）。"""
    # 準備
    _serve_note(fake_index, [doc_json("n1", "notes/n1.yaml", kind="note", data=N1_VALUE)])
    # 実行
    paths = _paths(make_client, "notes/n1.yaml", "n1")
    # 検証
    assert paths == frozenset(
        {"status", "summary", "#items[i1].body", "rows", "title", WHOLE_FILE_PATH}
    )


def _preview(handlers: Any, path: str, content: str) -> Any:
    """本文のプレビューを実行する。"""
    request = PreviewRequest(path=path, content=content)
    return asyncio.run(preview_document("sample", request, handlers=handlers))


def test_preview_document(fake_index: FakeIndex, make_handlers: Callable[..., Any]) -> None:
    """書き換えた値で変換する（正常系）。"""
    # 準備
    _serve_note(fake_index, [doc_json("n1", "notes/n1.yaml", kind="note", data=N1_VALUE)])
    content = dump_source({**N1_VALUE, "summary": "修正後の概要"})
    # 実行
    response = _preview(make_handlers(), "notes/n1", content)
    # 検証
    assert "修正後の概要" in response.markdown
    assert response.conversion_error is None
    assert response.fallback is False


def test_preview_document_when_yaml_invalid(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """YAML として読み込めない（正常系）。"""
    # 準備
    _serve_note(fake_index, [doc_json("n1", "notes/n1.yaml", kind="note", data=N1_VALUE)])
    content = "title: n1\nsummary: 概要\n\tstatus: draft\n"
    # 実行
    response = _preview(make_handlers(), "notes/n1", content)
    # 検証
    assert response.markdown is None
    assert response.conversion_error is not None
    assert response.conversion_error.reason == "invalid_yaml"
    assert response.conversion_error.line == 3


def test_preview_document_when_converter(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """変換のスクリプトを指す種類（正常系）。"""
    # 準備
    _serve_note(fake_index, [doc_json("n1", "notes/n1.yaml", kind="note", data=N1_VALUE)])
    fake_index.details[("sample", "notes/n1.yaml")] = {"markdown": "# 変換した\n"}
    # 実行
    response = _preview(make_handlers(), "notes/n1", dump_source(N1_VALUE))
    # 検証
    assert response.fallback is True
    assert "## 項目" in response.markdown


def test_preview_document_when_markdown(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """Markdown の文書（異常系）。"""
    # 準備
    guide = doc_json(
        "guide", "docs/files.yml", kind="files", body_path="guide.md", body="# ガイド\n"
    )
    _serve_note(fake_index, [guide])
    # 実行・検証
    with pytest.raises(PreviewNotYamlError, match=r"guide\.md"):
        _preview(make_handlers(), "guide.md", "# 書き換え\n")


def test_preview_document_when_missing(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """無い文書（異常系）。"""
    # 準備
    _serve_note(fake_index, [])
    # 実行・検証
    with pytest.raises(DocumentNotFoundError, match="no-such-doc"):
        _preview(make_handlers(), "no-such-doc", "title: x\n")
