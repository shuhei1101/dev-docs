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


def _page_items(items: Sequence[NavItem]) -> list[NavItem]:
    """入れ子の項目から page を並び順に平らに集める。"""
    pages: list[NavItem] = []
    for item in items:
        if item.kind == "page":
            pages.append(item)
        pages.extend(_page_items(item.items))
    return pages


def _mark_items(
    items: Sequence[NavItem], versions: Mapping[str, str], base_versions: Mapping[str, str]
) -> list[NavItem]:
    """項目を複製し、page に比較元からの変化を付ける。"""
    result: list[NavItem] = []
    for item in items:
        if item.kind == "group":
            children = _mark_items(item.items, versions, base_versions)
            result.append(item.model_copy(update={"items": children}))
            continue
        path = item.path or ""
        if path not in base_versions:
            change = "added"
        elif versions.get(path) != base_versions[path]:
            change = "modified"
        else:
            change = None
        result.append(item.model_copy(update={"change": change}))
    return result


def _same(a: NavItem, b: NavItem) -> bool:
    """比較元と開いているリビジョンで同じ項目か（`path` か `title` が同じ）。"""
    if a.kind != b.kind:
        return False
    return a.path == b.path if a.kind == "page" else a.title == b.title


def _insert_deleted(
    items: list[NavItem], base_items: Sequence[NavItem], deleted: Mapping[str, NavItem]
) -> list[NavItem]:
    """比較元の並びに合わせて、削除された page を差し込む（見つからない group は先頭の兄弟として扱う）。"""
    result = list(items)
    previous: NavItem | None = None
    for base_item in base_items:
        if base_item.kind == "group":
            match = next((i for i in result if _same(i, base_item)), None)
            if match is not None:
                index = result.index(match)
                result[index] = match.model_copy(
                    update={"items": _insert_deleted(match.items, base_item.items, deleted)}
                )
        elif base_item.path in deleted:
            marker = deleted[base_item.path or ""]
            anchor = next((i for i in result if previous is not None and _same(i, previous)), None)
            index = result.index(anchor) + 1 if anchor is not None else 0
            result.insert(index, marker)
        previous = base_item
    return result


def mark_nav_changes(
    tabs: Sequence[NavTab],
    base_tabs: Sequence[NavTab],
    *,
    versions: Mapping[str, str],
    base_versions: Mapping[str, str],
) -> list[NavTab]:
    """タブの page に比較元からの変化を付け、比較元にだけある文書を比較元の位置に差し込む。"""
    marked = [
        tab.model_copy(update={"items": _mark_items(tab.items, versions, base_versions)})
        for tab in tabs
    ]
    deleted = {
        item.path: item.model_copy(update={"change": "deleted"})
        for base_tab in base_tabs
        for item in _page_items(base_tab.items)
        if item.path is not None and item.path not in versions
    }
    if not deleted:
        return marked
    # 比較元のタブごとに、同じ title のタブへ差し込む。無ければ一番左のタブの末尾に置く
    for base_tab in base_tabs:
        target_index = next(
            (i for i, tab in enumerate(marked) if tab.title == base_tab.title), None
        )
        base_deleted = {
            path: item
            for path, item in deleted.items()
            if path in {p.path for p in _page_items(base_tab.items)}
        }
        if not base_deleted:
            continue
        if target_index is None:
            if not marked:
                continue
            target_index = 0
            tab = marked[0]
            marked[0] = tab.model_copy(update={"items": [*tab.items, *base_deleted.values()]})
        else:
            tab = marked[target_index]
            inserted = _insert_deleted(tab.items, base_tab.items, base_deleted)
            present = {p.path for p in _page_items(inserted)}
            missing = [item for path, item in base_deleted.items() if path not in present]
            marked[target_index] = tab.model_copy(update={"items": [*inserted, *missing]})
    return marked
