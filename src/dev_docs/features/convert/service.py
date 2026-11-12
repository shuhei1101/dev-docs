"""変換の選択と、表のキーの取り出し。"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from dev_docs.features.convert.embed import expand_embeds
from dev_docs.features.convert.markdown import item_heading, schema_to_markdown
from dev_docs.features.convert.types import (
    Converted,
    ConvertFailure,
    DocumentLink,
    RenderContext,
)
from dev_docs.features.documents.fields import is_markdown_body
from dev_docs.integrations.project_index.types import (
    DocumentDetail,
    IndexedDocument,
    SourceView,
)

TABLE_KEY_PATTERN = r"^<!-- dev-docs-table: (?P<key>.+) -->$"

TABLE_DATA_MARKER = "<!-- table: data -->"
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
FENCE = re.compile(r"^\s{0,3}(?P<mark>`{3,}|~{3,})")


def _strip_table_keys(markdown: str, kind: str) -> tuple[str, list[str]]:
    """表のキーのマーカーを取り除き、本文の表を出る順に表のキーと並べる。"""
    key_pattern = re.compile(TABLE_KEY_PATTERN)
    lines = markdown.splitlines(keepends=True)
    kept: list[str] = []
    keys: list[str] = []
    fence: str | None = None
    pending: str | None = None
    in_table = False
    for index, line in enumerate(lines):
        text = line.rstrip("\r\n")
        opened = FENCE.match(line)
        if fence is None and opened:
            fence = opened.group("mark")
            pending, in_table = None, False
        elif fence is not None:
            if (
                opened
                and opened.group("mark")[0] == fence[0]
                and len(opened.group("mark")) >= len(fence)
            ):
                fence = None
        else:
            matched = key_pattern.match(text)
            if matched:
                pending = matched.group("key")
                continue
            is_row = text.lstrip().startswith("|")
            if is_row and not in_table:
                following = lines[index + 1].rstrip("\r\n") if index + 1 < len(lines) else ""
                if SEPARATOR_ROW.match(following):
                    keys.append(pending or f"{kind}:table[{len(keys)}]")
                    pending, in_table = None, True
            elif not is_row:
                in_table = False
                if text.strip() and text != TABLE_DATA_MARKER:
                    pending = None
        kept.append(line)
    return "".join(kept), keys


class ConvertService:
    """文書の行の設定で変換を選んで Markdown を描き、埋め込みを展開して表のキーを取り出す。

    `converters[]` のスクリプトは project-index が実行して結果を返却するため、状態を持たない。
    """

    def _context(
        self,
        view: SourceView,
        document: IndexedDocument,
        documents: Sequence[IndexedDocument],
        linkable: Collection[str],
    ) -> RenderContext:
        """同じリビジョンの文書を ID・パスで参照するリンクのリンク先と、Issue の URL を集める。"""
        links: dict[str, DocumentLink] = {}
        by_id: dict[str, IndexedDocument] = {}
        for found in documents:
            link = DocumentLink(title=str(found.metadata.get("name") or found.id), path=found.path)
            by_id.setdefault(found.id, found)
            for key in (found.id, found.path, found.body_path):
                if key is not None:
                    links.setdefault(key, link)

        def heading(document_id: str, item: str) -> str | None:
            """ID の文書の値と行のスキーマで、項目の見出しを検索する。"""
            found = by_id.get(document_id)
            row = view.row(found.kind) if found is not None else None
            if found is None or row is None:
                return None
            return item_heading(found.data, row.schema, item)

        repository = view.github_repository
        return RenderContext(
            links=links,
            issue_url=f"https://github.com/{repository}/issues/" if repository else None,
            path=document.path,
            item_heading=heading,
            decisions=frozenset(linkable),
        )

    def render(
        self,
        view: SourceView,
        detail: DocumentDetail,
        documents: Sequence[IndexedDocument],
        *,
        linkable: Collection[str],
    ) -> str | ConvertFailure:
        """1 件の文書を、埋め込みのマーカーを残した Markdown にする。"""
        failure = detail.failure
        if failure is not None:
            return ConvertFailure(
                reason=failure.reason,
                kind=failure.kind,
                script=failure.script,
                detail=failure.detail,
                file=failure.file,
                line=failure.line,
                column=failure.column,
            )
        if detail.markdown is not None:
            return detail.markdown
        document = detail.document
        if document is None:
            return ConvertFailure(reason="invalid_yaml", kind="", detail="文書がありません")
        if is_markdown_body(document):
            return document.body
        row = view.row(document.kind)
        schema: Mapping[str, Any] = row.schema if row is not None else {}
        return schema_to_markdown(
            document, schema, self._context(view, document, documents, linkable)
        )

    def finish(self, markdown: str, kind: str, embedded: Mapping[str, Any | None]) -> Converted:
        """埋め込みを展開し、表のキーを取り出した変換の結果にする。"""
        stripped, keys = _strip_table_keys(expand_embeds(markdown, embedded), kind)
        return Converted(markdown=stripped, table_keys=keys)
