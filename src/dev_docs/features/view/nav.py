"""タブとサイドバーの組み立て。"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from dev_docs.features.documents.fields import get_field
from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import DocumentTable, ServedSource
from dev_docs.features.view.paths import page_path
from dev_docs.features.view.types import NavItem, NavTab

logger = logging.getLogger(__name__)

OTHER_GROUP = "その他"


def _link(document: Document, title: str | None = None) -> NavItem:
    """文書をサイドバーの `page` の項目にする。"""
    return NavItem(
        kind="page",
        title=title or str(document.metadata.get("name") or document.id),
        path=page_path(document),
    )


def _documents_of(documents: Sequence[Document], kind: str) -> list[Document]:
    """文書の行の文書を、文書のページのパスの昇順で返す。"""
    return sorted((d for d in documents if d.kind == kind), key=page_path)


def _auto(documents: Sequence[Document], spec: Mapping[str, Any]) -> list[NavItem]:
    """`auto` の文書を並べる（`group_by` があれば値ごとの `group` の項目にする）。"""
    found = _documents_of(documents, str(spec.get("document", "")))
    group_by = spec.get("group_by")
    if not group_by:
        return [_link(document) for document in found]
    buckets: dict[str, list[NavItem]] = {}
    for document in found:
        value = get_field(document.data, str(group_by))
        names = (
            [str(item) for item in value]
            if isinstance(value, list)
            else [str(value)]
            if value
            else [OTHER_GROUP]
        )
        for name in dict.fromkeys(names or [OTHER_GROUP]):
            buckets.setdefault(name, []).append(_link(document))
    return [NavItem(kind="group", title=name, items=links) for name, links in buckets.items()]


def _page(source: ServedSource, documents: Sequence[Document], value: str) -> Document | None:
    """`page` の値（行の id か `{行の id}/{文書の ID}`）が指す文書を探す。"""
    kind, _, doc_id = value.partition("/")
    rows = {row.id: row for row in source.config.documents}
    if kind not in rows:
        return None
    found = _documents_of(documents, kind)
    if not doc_id:
        return found[0] if len(found) == 1 else None
    return next((d for d in found if d.id == doc_id), None)


def _items(
    source: ServedSource, documents: Sequence[Document], items: Sequence[Mapping[str, Any]]
) -> list[NavItem]:
    """`items[]` を上から読み、サイドバーの項目の並びを作る。"""
    result: list[NavItem] = []
    for item in items:
        if "group" in item:
            children = _items(source, documents, item.get("items") or [])
            result.append(NavItem(kind="group", title=str(item["group"]), items=children))
        elif "page" in item:
            document = _page(source, documents, str(item["page"]))
            if document is None:
                logger.warning("nav の文書が無い（%s・%s）", source.id, item["page"])
                continue
            result.append(_link(document, item.get("title")))
        elif "auto" in item:
            auto = _auto(documents, item["auto"])
            title = item.get("title")
            # 見出しを持たない並びは、title があれば各行の名前を上書きする
            if title and all(entry.kind == "page" for entry in auto):
                auto = [_link_titled(entry, title) for entry in auto]
            result.extend(auto)
    return result


def _link_titled(entry: NavItem, title: str) -> NavItem:
    """`page` の項目の名前を上書きする。"""
    return NavItem(kind="page", title=title, path=entry.path)


def _tab_title(row: DocumentTable) -> str:
    """nav が無いときのタブの名前（行の `title`、無ければ `id`）。"""
    return row.title or row.id


def build_nav(source: ServedSource, documents: Sequence[Document]) -> list[NavTab]:
    """配信元の `nav` と文書から、上のタブとサイドバーを作る（`active` は全て `False`）。"""
    nav = source.config.nav
    # nav が無い: 有効な文書の行ごとに 1 つのタブを作る
    if not nav:
        return [
            NavTab(
                title=_tab_title(row),
                active=False,
                items=_auto(documents, {"document": row.id}),
            )
            for row in source.config.documents
            if row.enabled
        ]
    return [
        NavTab(
            title=str(tab["title"]),
            active=False,
            items=_items(source, documents, tab.get("items") or []),
        )
        for tab in nav.get("tabs", [])
    ]


def first_page(tab: NavTab) -> str | None:
    """タブのサイドバーの一番上の文書のページのパスを返す。"""

    def walk(items: Sequence[NavItem]) -> str | None:
        for item in items:
            # 文書の項目: そのパス
            if item.kind == "page":
                return item.path
            # 見出しの項目: 下を深さ優先でたどる
            found = walk(item.items)
            if found is not None:
                return found
        return None

    return walk(tab.items)
