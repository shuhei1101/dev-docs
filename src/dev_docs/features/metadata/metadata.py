"""配信元のメタデータを、project-index の読み取り API から種類ごとの行と列に組み立てる。"""

from __future__ import annotations

import asyncio
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ruamel.yaml import YAML

from dev_docs.integrations.project_index.client import ProjectIndexClient, build_source_view
from dev_docs.integrations.project_index.types import DocumentRow, IndexedDocument
from dev_docs.shared.api_model import ApiModel

__all__ = [
    "KIND_SPECS",
    "RULE_INDEX_KIND",
    "KeyMapping",
    "MetadataColumn",
    "MetadataKind",
    "MetadataResponse",
    "MetadataRow",
    "build_metadata",
    "key_mapping",
]

RULE_INDEX_KIND = "rule_index"
TERM_ALIAS_TYPE = "term"
DIRECT_COMMIT_MARK = "✓"
# 共通のキー（`commonKeys`）。それ以外の列は文書の値から参照する
COMMON_KEYS = frozenset({"id", "name", "description", "tags", "main_tags", "aliases", "alias_type"})
RULE_INDEX_HINT = "documents:\n  - id: rule_index\n    paths: [rules.yaml]\n    records: rules\n"
_TOP_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ARRAY_ITEM = re.compile(r"^(\w+)\[\]\.(\w+)$")

MetadataKindId = Literal["terms", "aliases", "tags", "rules", "config", "files"]
ColumnType = Literal["text", "list"]


@dataclass(frozen=True, slots=True)
class _ColumnSpec:
    """列 1 つの決まり（`editable` は元のキーへ戻せるかを確認する前の値）。"""

    key: str
    label: str
    type: ColumnType
    editable: bool


@dataclass(frozen=True, slots=True)
class _KindSpec:
    """種類 1 つのタブの名前・列・追加と削除を受けるか。"""

    id: MetadataKindId
    title: str
    columns: tuple[_ColumnSpec, ...]
    can_change_rows: bool


KIND_SPECS: tuple[_KindSpec, ...] = (
    _KindSpec(
        "terms",
        "用語集",
        (
            _ColumnSpec("name", "用語", "text", True),
            _ColumnSpec("aliases", "別名", "list", True),
            _ColumnSpec("description", "説明", "text", True),
        ),
        True,
    ),
    _KindSpec(
        "aliases",
        "エイリアス",
        (
            _ColumnSpec("name", "名前", "text", True),
            _ColumnSpec("aliases", "別名", "list", True),
            _ColumnSpec("path", "文書", "text", False),
        ),
        False,
    ),
    _KindSpec(
        "tags",
        "タグ",
        (_ColumnSpec("path", "文書", "text", False), _ColumnSpec("tags", "タグ", "list", True)),
        False,
    ),
    _KindSpec(
        "rules",
        "rule-inject の索引",
        (
            _ColumnSpec("rule", "規約", "text", True),
            _ColumnSpec("paths", "適用するパス", "list", True),
            _ColumnSpec("tools", "ツール", "list", True),
            _ColumnSpec("args", "引数", "text", False),
        ),
        True,
    ),
    _KindSpec(
        "config",
        "配信元の設定",
        (
            _ColumnSpec("id", "種類", "text", False),
            _ColumnSpec("paths", "パス", "list", False),
            _ColumnSpec("records", "行", "text", False),
            _ColumnSpec("alias_type", "エイリアスの種類", "text", False),
            _ColumnSpec("direct_commit", "直コミット", "text", False),
        ),
        False,
    ),
    _KindSpec(
        "files",
        "管理用の YAML",
        (
            _ColumnSpec("records", "行", "text", False),
            _ColumnSpec("path", "ファイル", "text", False),
            _ColumnSpec("description", "概要", "text", True),
        ),
        False,
    ),
)


class MetadataColumn(ApiModel):
    """表の列 1 つ。"""

    key: str
    label: str
    type: ColumnType
    # 元のキーへ戻せて修正できる列か
    editable: bool


class MetadataRow(ApiModel):
    """表の行 1 つ。"""

    id: str
    doc_kind: str | None
    doc_path: str | None
    version: str | None
    # 文書の種類が `writeApiKinds` にあるか
    editable: bool
    values: dict[str, str | list[str]]


class MetadataKind(ApiModel):
    """タブ 1 つ分の列と行。"""

    id: MetadataKindId
    title: str
    served: bool
    hint: str | None
    columns: list[MetadataColumn]
    can_add: bool
    can_delete: bool
    create_kind: str | None
    rows: list[MetadataRow]


class MetadataResponse(ApiModel):
    """メタデータの取得の応答。"""

    source: str
    branch: str | None
    kinds: list[MetadataKind]


@dataclass(frozen=True, slots=True)
class KeyMapping:
    """共通のキーを文書の実際のキーへ戻す対応。"""

    key: str
    # `{キー}[].{項目}` の項目。最上位のキーそのものは `None`
    item: str | None


def key_mapping(metadata: Mapping[str, str] | None, column: str) -> KeyMapping | None:
    """配信元の設定の行の `metadata` から、列のキーを戻す先を求める（戻せない対応は `None`）。"""
    target = (metadata or {}).get(column)
    # 対応が無い: 同じ名前の最上位のキー
    if target is None:
        return KeyMapping(column, None)
    # 最上位のキー
    if _TOP_KEY.match(target):
        return KeyMapping(target, None)
    # オブジェクトの配列の項目
    matched = _ARRAY_ITEM.match(target)
    if matched:
        return KeyMapping(matched.group(1), matched.group(2))
    # 入れ子のパス・絞り込み: 戻せない
    return None


def _text(value: Any) -> str:
    """値を表のセルの文字列にする（オブジェクトは YAML の文字列）。"""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        dumper = YAML(typ="safe", pure=True)
        dumper.default_flow_style = False
        buffer = io.StringIO()
        dumper.dump(value, buffer)
        return buffer.getvalue().strip()
    return str(value)


def _list(value: Any) -> list[str]:
    """値を文字列の配列にする（`{name: ...}` の要素は `name` を取る）。"""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(item.get("name", "")) if isinstance(item, Mapping) else str(item) for item in items]


def _cell(spec: _ColumnSpec, document: IndexedDocument, kind_id: MetadataKindId) -> Any:
    """文書から列の元の値を取り出す。"""
    if spec.key == "path":
        # 管理用の YAML は本文のファイル、ほかは文書のファイル
        return document.body_path if kind_id == "files" and document.body_path else document.path
    if spec.key == "records":
        return document.kind
    if spec.key in COMMON_KEYS:
        return document.metadata.get(spec.key)
    return document.data.get(spec.key)


def _row(spec: _KindSpec, document: IndexedDocument, write_kinds: set[str]) -> MetadataRow:
    """文書 1 件を行にする。"""
    values: dict[str, str | list[str]] = {}
    for column in spec.columns:
        raw = _cell(column, document, spec.id)
        values[column.key] = _list(raw) if column.type == "list" else _text(raw)
    return MetadataRow(
        id=document.id,
        doc_kind=document.kind,
        doc_path=document.body_path or document.path,
        version=document.version,
        editable=document.kind in write_kinds,
        values=values,
    )


def _columns(
    spec: _KindSpec, documents: list[IndexedDocument], mappings: Mapping[str, Mapping[str, str]]
) -> list[MetadataColumn]:
    """列の `editable` を、行の文書の種類ごとの対応で決める。"""
    result: list[MetadataColumn] = []
    for column in spec.columns:
        # 戻せない種類の行が 1 つでもあれば修正させない
        editable = column.editable and all(
            key_mapping(mappings.get(document.kind), column.key) is not None
            for document in documents
        )
        result.append(
            MetadataColumn(key=column.key, label=column.label, type=column.type, editable=editable)
        )
    return result


def _is_files_row(row: DocumentRow, raw_rows: Mapping[str, Mapping[str, Any]]) -> bool:
    """`records` と `body_file` を持つ、管理用の YAML の行か。"""
    raw = raw_rows.get(row.id) or {}
    return bool(row.records) and bool(raw.get("body_file"))


def _config_rows(rows: list[DocumentRow], write_kinds: set[str]) -> list[MetadataRow]:
    """配信元の設定の `documents[]` を行にする（全て修正できない）。"""
    return [
        MetadataRow(
            id=row.id,
            doc_kind=None,
            doc_path=None,
            version=None,
            editable=False,
            values={
                "id": row.id,
                "paths": list(row.paths),
                "records": _text(row.records),
                "alias_type": _text(row.alias_type),
                "direct_commit": DIRECT_COMMIT_MARK if row.id in write_kinds else "",
            },
        )
        for row in rows
    ]


async def build_metadata(client: ProjectIndexClient, source_id: str) -> MetadataResponse:
    """配信元の設定・文書の一覧・リビジョンの一覧・端末の設定を同時に取得し、種類ごとの行と列にする。"""
    # 4 つの問い合わせを同時に投げ、最初の例外（配信元が無い・つながらない）をそのまま伝える
    try:
        async with asyncio.TaskGroup() as group:
            config_task = group.create_task(client.source_config(source_id))
            refs_task = group.create_task(client.refs(source_id, commits=0))
            docs_task = group.create_task(client.list_documents(source_id, values=True))
            settings_task = group.create_task(client.settings_sources())
    except ExceptionGroup as group_error:
        raise group_error.exceptions[0] from None
    view = build_source_view(source_id, config_task.result(), refs_task.result())
    documents = docs_task.result().documents
    write_kinds = set(settings_task.result().write_api_kinds.get(source_id, []))
    raw_rows = {
        str(row.get("id")): row for row in config_task.result().value.get("documents") or []
    }
    mappings = {row.id: row.metadata for row in view.documents}
    files_kinds = {row.id for row in view.documents if _is_files_row(row, raw_rows)}
    served_kinds = {row.id for row in view.documents}
    term_kind = next(
        (row.id for row in view.documents if row.alias_type == TERM_ALIAS_TYPE and row.records),
        None,
    )

    # 種類ごとに行の文書を振り分ける
    groups: dict[MetadataKindId, list[IndexedDocument]] = {
        "terms": [d for d in documents if d.metadata.get("alias_type") == TERM_ALIAS_TYPE],
        "aliases": [
            d for d in documents if d.metadata.get("alias_type") not in (None, "", TERM_ALIAS_TYPE)
        ],
        "tags": list(documents),
        "rules": [d for d in documents if d.kind == RULE_INDEX_KIND],
        "config": [],
        "files": [d for d in documents if d.kind in files_kinds],
    }
    create_kinds: dict[MetadataKindId, str | None] = {
        "terms": term_kind,
        "rules": RULE_INDEX_KIND if RULE_INDEX_KIND in served_kinds else None,
    }

    kinds: list[MetadataKind] = []
    for spec in KIND_SPECS:
        served = spec.id != "rules" or RULE_INDEX_KIND in served_kinds
        create_kind = create_kinds.get(spec.id) if spec.can_change_rows else None
        rows = (
            _config_rows(view.documents, write_kinds)
            if spec.id == "config"
            else [_row(spec, document, write_kinds) for document in groups[spec.id]]
        )
        columns = (
            [
                MetadataColumn(key=c.key, label=c.label, type=c.type, editable=False)
                for c in spec.columns
            ]
            if spec.id == "config"
            else _columns(spec, groups[spec.id], mappings)
        )
        kinds.append(
            MetadataKind(
                id=spec.id,
                title=spec.title,
                served=served,
                hint=None if served else RULE_INDEX_HINT,
                columns=columns,
                can_add=create_kind is not None and create_kind in write_kinds,
                can_delete=spec.can_change_rows and served,
                create_kind=create_kind,
                rows=rows,
            )
        )
    return MetadataResponse(source=source_id, branch=view.default_ref, kinds=kinds)
