"""文書の取得の本文の編集の情報と、本文のプレビュー。"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from dev_docs.features.convert.embed import embed_paths
from dev_docs.features.convert.markdown import HEADING_KEYS
from dev_docs.features.convert.service import ConvertService
from dev_docs.features.convert.types import ConvertFailure
from dev_docs.features.documents.fields import is_markdown_body
from dev_docs.features.view.paths import find_page
from dev_docs.features.view.types import ConversionError, DocumentResponse
from dev_docs.integrations.project_index.client import ProjectIndexClient, build_source_view
from dev_docs.integrations.project_index.types import (
    DocumentDetail,
    DocumentList,
    IndexedDocument,
    SourceView,
    parse_document_list,
)
from dev_docs.shared.api_model import ApiModel
from dev_docs.shared.errors import DevDocsError, DocumentNotFoundError, ProjectIndexUnreachableError
from dev_docs.shared.yaml_io import YamlLoadError, dump_roundtrip, load_yaml

if TYPE_CHECKING:
    from ruamel.yaml.comments import CommentedMap

    from dev_docs.main import Handlers

# 直コミットの `edits[].values` のファイル全体の編集のキー
WHOLE_FILE_PATH = "@file"
# 本文のプレビュー全体を打ち切る秒数（文書の取得と同じ非機能要件の document_fetch_timeout）
PREVIEW_TIMEOUT_SEC: float = 70
# Markdown の文字列の項目のスキーマの `contentMediaType`
MARKDOWN_MEDIA_TYPE = "text/markdown"
# 本文のファイルが Markdown の文書の拡張子
MARKDOWN_SUFFIX = ".md"

EditBlockType = Literal["string", "enum", "markdown", "table"]


class EditBlock(ApiModel):
    """表示した場所で修正できる項目 1 つ。"""

    path: str
    label: str
    type: EditBlockType
    # 文書の取得の `markdown` のうち、この項目を描いた範囲
    markdown: str
    # 今の値（`table` は行ごとの列の値）
    value: str | list[dict[str, str]]
    options: list[str] | None = None
    columns: list[str] | None = None


class DocumentEdit(ApiModel):
    """文書の取得の `edit`（文書の画面で本文を編集するときの元の内容と項目）。"""

    doc_id: str
    kind: str
    file_path: str
    version: str
    base_commit: str
    language: Literal["yaml", "markdown"]
    source: str
    blocks: list[EditBlock]
    title_block: EditBlock | None


class PreviewRequest(ApiModel):
    """POST `/_api/sources/{source}/preview` の本文。"""

    path: str
    content: str


class PreviewResponse(ApiModel):
    """POST `/_api/sources/{source}/preview` の 200 の応答。"""

    markdown: str | None
    conversion_error: ConversionError | None
    # `converters[]` を指す種類を、スキーマ駆動の変換で描いたか
    fallback: bool


@dataclass(kw_only=True)
class PreviewNotYamlError(DevDocsError):
    """YAML の文書でない文書の本文のプレビューの要求。"""

    status: ClassVar[int] = 400


# 文書の取得の応答の `edit` の型を解決する（`types.py` は循環の import を使用せずに名前だけで参照する）
DocumentResponse.model_rebuild(_types_namespace={"DocumentEdit": DocumentEdit})


def dump_source(value: Mapping[str, Any]) -> str:
    """文書の値を、キーの順のままブロック形式の YAML の文字列にする。"""
    return dump_roundtrip(cast("CommentedMap", value))


def _title_of(sub: Mapping[str, Any], key: str) -> str:
    """スキーマの `title`（無ければキー）を項目の名前にする。"""
    return str(sub.get("title") or key)


def _is_string_schema(sub: Any) -> bool:
    """スキーマが文字列（`enum` を含む）の項目か。"""
    return isinstance(sub, Mapping) and (sub.get("type") == "string" or "enum" in sub)


def _scalar_type(sub: Mapping[str, Any]) -> EditBlockType:
    """文字列の項目のスキーマから、編集の部品の種類を選ぶ。"""
    if "enum" in sub:
        return "enum"
    if sub.get("contentMediaType") == MARKDOWN_MEDIA_TYPE:
        return "markdown"
    return "string"


def _scalar_block(path: str, label: str, value: str, sub: Mapping[str, Any]) -> EditBlock:
    """文字列の項目の編集の部品を作る。"""
    kind = _scalar_type(sub)
    options = [str(option) for option in sub["enum"]] if kind == "enum" else None
    return EditBlock(path=path, label=label, type=kind, markdown="", value=value, options=options)


def _element_properties(sub: Mapping[str, Any]) -> Mapping[str, Any]:
    """配列のスキーマの要素の `properties` を返却する（無ければ空）。"""
    items = sub.get("items")
    properties = items.get("properties") if isinstance(items, Mapping) else None
    return properties if isinstance(properties, Mapping) else {}


def _table_block(
    key: str, label: str, rows: Sequence[Any], properties: Mapping[str, Any]
) -> EditBlock | None:
    """要素が文字列の項目だけを持つオブジェクトの配列を、編集できる表にする（該当しなければ `None`）。"""
    if not properties or not all(_is_string_schema(sub) for sub in properties.values()):
        return None
    if not all(isinstance(row, Mapping) for row in rows):
        return None
    columns = list(properties)
    values: list[dict[str, str]] = []
    for row in rows:
        # 文字列でない値を持つ行: 表では修正できないため、ファイル全体の編集に回す
        if any(not isinstance(row.get(column, ""), str) for column in columns):
            return None
        values.append({column: str(row.get(column, "")) for column in columns})
    return EditBlock(
        path=key, label=label, type="table", markdown="", value=values, columns=columns
    )


def _keyed_blocks(key: str, rows: Sequence[Any], sub: Mapping[str, Any]) -> list[EditBlock]:
    """`x-key` を持つオブジェクトの配列の、要素の中の文字列の項目を並べる。"""
    x_key = sub.get("x-key")
    properties = _element_properties(sub)
    blocks: list[EditBlock] = []
    for element in rows:
        if not isinstance(element, Mapping) or element.get(x_key) is None:
            continue
        label_key = element[x_key]
        for name, child_sub in properties.items():
            child = element.get(name)
            # 内部向けの項目・文字列でない値・値の無い項目は、表示した場所では修正しない
            if not isinstance(child_sub, Mapping) or child_sub.get("x-hidden"):
                continue
            if not isinstance(child, str) or not _is_string_schema(child_sub):
                continue
            blocks.append(
                _scalar_block(
                    f"#{key}[{label_key}].{name}",
                    f"{label_key} の {_title_of(child_sub, name)}",
                    child,
                    child_sub,
                )
            )
    return blocks


def _blocks_of(key: str, value: Any, sub: Mapping[str, Any]) -> list[EditBlock]:
    """最上位の項目 1 つを、表示した場所で修正できる項目にする（該当しなければ空）。"""
    label = _title_of(sub, key)
    # 文字列: スキーマの型で入力欄・選択肢・Markdown のエディタを選ぶ
    if isinstance(value, str):
        return [_scalar_block(key, label, value, sub)] if _is_string_schema(sub) else []
    # オブジェクトの配列: セクションで描く `x-key` の配列は要素の中の項目、文字列の列だけなら表
    if isinstance(value, list) and value and all(isinstance(row, Mapping) for row in value):
        if sub.get("x-key") and sub.get("x-shape") == "sections":
            return _keyed_blocks(key, value, sub)
        table = _table_block(key, label, value, _element_properties(sub))
        if table is not None:
            return [table]
        if sub.get("x-key"):
            return _keyed_blocks(key, value, sub)
    # 入れ子のオブジェクト・数・真偽値・それ以外の配列: ファイル全体の編集で修正する
    return []


def collect_blocks(
    value: Mapping[str, Any],
    schema: Mapping[str, Any],
    item_ranges: Sequence[tuple[str, str]] | None,
) -> tuple[list[EditBlock], EditBlock | None]:
    """表示した場所で修正できる項目と、文書のタイトルに描く項目を取り出す。"""
    properties: Mapping[str, Any] = schema.get("properties") or {}
    heading_key = next(
        (key for key in HEADING_KEYS if isinstance(value.get(key), str) and value.get(key)), None
    )
    blocks: list[EditBlock] = []
    title: EditBlock | None = None
    for key, sub in properties.items():
        if key not in value or not isinstance(sub, Mapping):
            continue
        # 内部向けの項目・図: 表示した場所では修正しない
        if sub.get("x-hidden") or sub.get("x-shape") == "diagram":
            continue
        found = _blocks_of(key, value[key], sub)
        # 共通のキー `name` に該当する最上位のキー: 文書のタイトルで修正する
        if key == heading_key and found:
            title = found[0]
            continue
        blocks.extend(found)
    # 描いた範囲が無い: スキーマの順のまま、範囲を空で返却する
    if item_ranges is None:
        return blocks, title
    # 描いた範囲がある: 描いた項目だけを描いた順に並べ、範囲の Markdown を付ける
    ranges = dict(item_ranges)
    order = {path: position for position, (path, _) in enumerate(item_ranges)}
    rendered = sorted(
        (block for block in blocks if block.path in ranges), key=lambda b: order[b.path]
    )
    blocks = [block.model_copy(update={"markdown": ranges[block.path]}) for block in rendered]
    if title is not None:
        title = (
            title.model_copy(update={"markdown": ranges[title.path]})
            if title.path in ranges
            else None
        )
    return blocks, title


def _row_config(config: Mapping[str, Any], kind: str) -> Mapping[str, Any]:
    """配信元の設定の `documents[]` から、種類の行を返却する（無ければ空）。"""
    for row in config.get("documents") or []:
        if isinstance(row, Mapping) and row.get("id") == kind:
            return row
    return {}


def build_document_edit(
    view: SourceView,
    config: Mapping[str, Any],
    detail: DocumentDetail,
    *,
    write_api_kinds: Collection[str],
    base_commit: str,
    version: str,
    item_ranges: Sequence[tuple[str, str]],
) -> DocumentEdit | None:
    """本文を編集できる文書の `edit` を組み立て、編集できない文書は `None` を返却する。"""
    document = detail.document
    if document is None or detail.failure is not None:
        return None
    # 書き込みの API が断る種類・SQLite の行の種類は編集させない
    if document.kind not in write_api_kinds or _row_config(config, document.kind).get("sqlite"):
        return None
    common = {
        "doc_id": document.id,
        "kind": document.kind,
        "file_path": document.body_path or document.path,
        "version": version,
        "base_commit": base_commit,
    }
    # 本文のファイルを持つ文書: Markdown の本文で、本文を直コミットする種類のときだけ編集させる
    if document.body_path is not None:
        metadata_only = (config.get("directCommit") or {}).get("metadataOnlyKinds") or []
        suffix = PurePosixPath(document.body_path).suffix.lower()
        if suffix != MARKDOWN_SUFFIX or document.kind in metadata_only:
            return None
        return DocumentEdit(
            **common,
            language="markdown",
            source=document.body,
            blocks=[],
            title_block=None,
        )
    # 変換のスクリプトを指す種類: スキーマ駆動で描いていないため、ファイル全体の編集だけにする
    if detail.markdown is not None:
        blocks: list[EditBlock] = []
        title: EditBlock | None = None
    else:
        row = view.row(document.kind)
        blocks, title = collect_blocks(
            document.data, row.schema if row is not None else {}, item_ranges
        )
    return DocumentEdit(
        **common,
        language="yaml",
        source=dump_source(document.data),
        blocks=blocks,
        title_block=title,
    )


async def _source_snapshot(
    client: ProjectIndexClient, source_id: str, ref: str | None
) -> tuple[SourceView, Mapping[str, Any], DocumentList]:
    """配信元の表示の設定・配信元の設定の値・リビジョンの文書の一覧を同時に取得する。"""
    refs, config, listing = await asyncio.gather(
        client.refs(source_id, commits=0),
        client.source_config(source_id),
        client.fetch_document_list(source_id, ref=ref),
    )
    view = build_source_view(source_id, config, refs)
    listed = await asyncio.to_thread(
        parse_document_list, source_id, listing, record_kinds=view.record_kinds()
    )
    return view, config.value, listed


async def body_item_paths(
    client: ProjectIndexClient,
    source_id: str,
    doc_path: str,
    doc_id: str,
    *,
    base_commit: str,
    convert: ConvertService,
) -> frozenset[str]:
    """編集を始めたときのコミットの文書で、`body` の変更に指定できる項目のパスを返却する。"""
    (view, config, listed), settings, detail = await asyncio.gather(
        _source_snapshot(client, source_id, base_commit),
        client.settings_sources(),
        client.document(source_id, doc_path, ref=base_commit, document_id=doc_id),
    )
    ranges: list[tuple[str, str]] = []
    rendered = await asyncio.to_thread(
        convert.render, view, detail, listed.documents, linkable=(), item_ranges=ranges
    )
    # 変換に失敗した文書: 文書の取得も `edit` を返却しないため、どの項目も修正させない
    if isinstance(rendered, ConvertFailure):
        return frozenset()
    listed_document = next((item for item in listed.documents if item.id == doc_id), None)
    edit = build_document_edit(
        view,
        config,
        detail,
        write_api_kinds=settings.write_api_kinds.get(source_id, []),
        base_commit=base_commit,
        version=listed_document.version if listed_document is not None else "",
        item_ranges=ranges,
    )
    if edit is None:
        return frozenset()
    paths = {block.path for block in edit.blocks}
    if edit.title_block is not None:
        paths.add(edit.title_block.path)
    paths.add(WHOLE_FILE_PATH)
    return frozenset(paths)


def _invalid_yaml(document: IndexedDocument, error: YamlLoadError) -> ConversionError:
    """書き換えた YAML を読み込めない位置と理由を、文書の取得と同じ `conversionError` にする。"""
    return ConversionError(
        reason="invalid_yaml",
        kind=document.kind,
        detail=error.reason,
        file=error.file,
        line=error.line,
        column=error.column,
    )


async def _embedded(
    client: ProjectIndexClient, source_id: str, markdown: str
) -> dict[str, Any | None]:
    """埋め込みのマーカーのパスごとに、既定のブランチの文書の値を取る。"""
    paths = embed_paths(markdown)

    async def fetch(path: str) -> Any | None:
        try:
            detail = await client.document(source_id, path)
        except DocumentNotFoundError:
            return None
        return None if detail.document is None else detail.document.data

    values = await asyncio.gather(*(fetch(path) for path in paths))
    return dict(zip(paths, values, strict=True))


async def preview_document(
    source_id: str, request: PreviewRequest, *, handlers: Handlers
) -> PreviewResponse:
    """書き換えた YAML を、文書の取得と同じスキーマ駆動の変換で Markdown にする。"""
    try:
        async with asyncio.timeout(PREVIEW_TIMEOUT_SEC):
            return await _preview(source_id, request, handlers=handlers)
    except TimeoutError as error:
        raise ProjectIndexUnreachableError(
            address=handlers.project_index.address,
            reason=f"{PREVIEW_TIMEOUT_SEC:g} 秒以内に応答がありませんでした",
            kind="timeout",
        ) from error


async def _preview(
    source_id: str, request: PreviewRequest, *, handlers: Handlers
) -> PreviewResponse:
    """本文のプレビューの本体（制限時間の外側は `preview_document` が持つ）。"""
    client = handlers.project_index
    view, _, listed = await _source_snapshot(client, source_id, None)
    document = find_page(listed.documents, request.path)
    if document is None:
        raise DocumentNotFoundError(
            message=f"文書がありません: {request.path}", missing=[request.path]
        )
    # 本文のファイルを持つ文書: ファイル全体の編集の値を Markdown のまま描くため、プレビューを断る
    if document.body_path is not None or is_markdown_body(document):
        raise PreviewNotYamlError(message=f"YAML の文書ではありません: {request.path}")
    detail = await client.document(
        view.id,
        document.path,
        document_id=document.id if document.record_index is not None else None,
    )
    # project-index が変換の結果を返却した種類: 配信元の変換は書き換えた内容を描けない
    fallback = detail.markdown is not None
    try:
        value = load_yaml(request.content, file=document.path)
    except YamlLoadError as error:
        return PreviewResponse(
            markdown=None, conversion_error=_invalid_yaml(document, error), fallback=fallback
        )
    # 最上位が辞書でない: 文書の値にできないため、読み込めない位置を先頭にする
    if not isinstance(value, Mapping):
        problem = YamlLoadError("最上位が辞書ではありません", file=document.path, line=1, column=1)
        return PreviewResponse(
            markdown=None, conversion_error=_invalid_yaml(document, problem), fallback=fallback
        )
    rewritten = dataclasses.replace(detail.document or document, data=dict(value))
    rendered = await asyncio.to_thread(
        handlers.converter.render,
        view,
        DocumentDetail(document=rewritten),
        listed.documents,
        linkable=(),
    )
    if isinstance(rendered, ConvertFailure):
        return PreviewResponse(
            markdown=None,
            conversion_error=ConversionError(
                reason=rendered.reason,
                kind=rendered.kind,
                detail=rendered.detail,
                script=rendered.script,
                file=rendered.file,
                line=rendered.line,
                column=rendered.column,
            ),
            fallback=fallback,
        )
    embedded = await _embedded(client, view.id, rendered)
    converted = handlers.converter.finish(rendered, document.kind, embedded)
    return PreviewResponse(markdown=converted.markdown, conversion_error=None, fallback=fallback)
