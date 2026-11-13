"""スキーマ駆動の Markdown への変換。"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from dev_docs.features.convert.decisions import DECISIONS_KEY
from dev_docs.features.convert.diagrams import er_table_titles, render_diagram
from dev_docs.features.convert.inline import (
    heading_anchor,
    link_decisions,
    link_reference,
    rewrite_text,
)
from dev_docs.features.convert.types import DiagramHead, DiagramKind, RenderContext
from dev_docs.integrations.project_index.types import IndexedDocument

MAX_HEADING_LEVEL = 6
FIRST_HEADING_LEVEL = 2
HEADING_KEYS = ("title", "name")
LEAD_KEYS = ("lead", "description")
ATTRIBUTE_MIN = 3
LONG_VALUE_CHARS = 100
WIDE_KEYS = ("description", "summary", "notes")
LABEL_KEYS = ("label", "name")
DIAGRAM_HIDDEN_KEYS = ("id",)
TEST_FILE_KEYS = ("test_file", "test_files")
EXAMPLE_SUFFIX = "_example"
CHECK_MARK = "✓"
CELL_JOINER = "・"
OBJECT_JOINER = "、"
NO_DATE = "-"
# ER 図の実体の列を補うテーブルを持つ、文書のキー
ER_TABLES_KEY = "tables"
# 項目のパスの 1 階層（`{キー}` か `{キー}[{x-key の値}]`）
ITEM_STEP = re.compile(r"(?P<key>[^.\[\]]+)(?:\[(?P<label>[^\]]*)\])?")


def _is_empty(value: Any) -> bool:
    """値が空（組み立てずに飛ばす）かを返却する。"""
    return value is None or value == "" or value == [] or value == {}


def _scalar(value: Any) -> str:
    """スカラーを文字列にする（真偽の値は `CHECK_MARK` か空）。"""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bool):
        return CHECK_MARK if value else ""
    return str(value)


def _is_scalar(value: Any) -> bool:
    """辞書でも配列でもない値かを返却する。"""
    return not isinstance(value, Mapping | list)


def _is_rows(value: Any) -> bool:
    """辞書だけの配列かを返却する。"""
    return isinstance(value, list) and bool(value) and all(isinstance(v, Mapping) for v in value)


def _is_hidden(sub: Any) -> bool:
    """スキーマが `x-hidden: true` を持つかを返却する。"""
    return isinstance(sub, Mapping) and sub.get("x-hidden") is True


def _items(value: Any) -> list[Mapping[str, Any]]:
    """配列の値のうち、辞書の要素だけを取り出す（配列でなければ空）。"""
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _escape_cell(text: str) -> str:
    """セルの `|` をエスケープし、改行を `<br>` にする。"""
    return text.replace("\r\n", "\n").replace("|", "\\|").replace("\n", "<br>")


def _foreign_key(reference: str, context: RenderContext | None) -> str:
    """外部キーの `{分類}/{テーブル}.{カラム}` を、参照先のテーブルへのリンクにする（見つからなければ文字のまま）。"""
    if context is None:
        return _escape_cell(reference)
    table = reference.rpartition(".")[0]
    classification, _, name = table.rpartition("/")
    # 他の分類のテーブル: 同じフォルダの分類の文書へのリンク
    if classification:
        folder = posixpath.dirname(context.path)
        link = context.links.get(posixpath.join(folder, f"{classification}.yaml"))
        if link is None:
            return _escape_cell(reference)
        relative = quote(posixpath.relpath(link.path, folder or "."), safe="/")
        return f"[{reference}]({relative})"
    # 同じ文書のテーブル: 物理名でも論理名にしてから、論理名で見出しのアンカーへのリンク
    heading = context.anchors.get(context.table_titles.get(name, name))
    if heading is None:
        return _escape_cell(reference)
    return f"[{reference}](#{heading_anchor(heading)})"


def _object_cell(value: Mapping[str, Any], context: RenderContext | None) -> str:
    """オブジェクトのセル（外部キーは参照先のテーブルへのリンク、それ以外は `キー: 値` の並び）にする。"""
    if isinstance(value.get("table"), str):
        return _foreign_key(value["table"], context)
    return _escape_cell(
        OBJECT_JOINER.join(f"{key}: {_scalar(item)}" for key, item in value.items())
    )


def _cell(value: Any, context: RenderContext | None) -> str:
    """表のセルの文字列にする。"""
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return _object_cell(value, context)
    if isinstance(value, list):
        # 文字列のリスト: `・` で繋ぐ。オブジェクトを含む: 要素ごとに改行で繋ぐ
        if all(_is_scalar(item) for item in value):
            return CELL_JOINER.join(_cell(item, context) for item in value)
        return "<br>".join(_cell(item, context) for item in value)
    if isinstance(value, str) and context is not None:
        link = link_reference(value, context)
        if link is not None:
            return link
    return _escape_cell(_scalar(value))


def render_table(
    rows: Sequence[Mapping[str, Any]],
    item_schema: Mapping[str, Any],
    *,
    table_key: str,
    context: RenderContext | None = None,
    closed: bool = False,
    first: str | None = None,
    hidden: Sequence[str] = (),
) -> str:
    """オブジェクトのリストを、mdmark の表のマーカーつきの Markdown の表にする。"""
    properties: Mapping[str, Any] = item_schema.get("properties") or {}
    keys = list(properties)
    keys.extend(key for row in rows for key in row if key not in keys)
    keys = list(dict.fromkeys(keys))
    columns = [
        key
        for key in keys
        if not _is_hidden(properties.get(key)) and any(not _is_empty(row.get(key)) for row in rows)
    ]
    if not columns:
        return ""
    if first in columns:
        columns.remove(first)
        columns.insert(0, first)

    def title(key: str) -> str:
        sub = properties.get(key)
        return str(sub.get("title") or key) if isinstance(sub, Mapping) else key

    # 表のマーカーの引数（mdmark は先頭の列を隠せないため、先頭の列は隠す列に入れない）
    marker = ["data"]
    if closed:
        marker.append("closed")
    hide = [title(key) for key in columns[1:] if key in hidden and " " not in title(key)]
    if hide:
        marker.append(f"+columns hide={','.join(hide)}")
    wide = [title(key) for key in columns if key in WIDE_KEYS and " " not in title(key)]
    if wide:
        marker.append(f"wide={','.join(wide)}")
    lines = [
        f"<!-- dev-docs-table: {table_key} -->",
        f"<!-- table: {' '.join(marker)} -->",
        f"| {' | '.join(title(key) for key in columns)} |",
        f"| {' | '.join('---' for _ in columns)} |",
    ]

    def cell(row: Mapping[str, Any], key: str) -> str:
        value = row.get(key)
        # 検討事項の列: リンク先の決まる ID を先にリンクにする
        if key == DECISIONS_KEY and isinstance(value, list) and context is not None:
            value = link_decisions(value, context)
        return _cell(value, context)

    lines.extend(f"| {' | '.join(cell(row, key) for key in columns)} |" for row in rows)
    lines.append("<!-- /table -->")
    return "\n".join(lines)


def render_attributes(
    pairs: Sequence[tuple[str, Any]], context: RenderContext, head: DiagramHead
) -> str:
    """名前と値の組を「項目 / 値」の 2 列の表にし、長い値は行の詳細に入れる。"""
    rows: list[str] = []
    details: list[str] = []
    for position, (name, value) in enumerate(pairs, start=1):
        text = _scalar(value)
        link = link_reference(text, context) if isinstance(value, str) else None
        # 長い値・複数行の値: セルは最初の行の先頭だけにし、全文は行の詳細に配置する
        if link is None and (len(text) > LONG_VALUE_CHARS or "\n" in text):
            cell = f"{_escape_cell(text.splitlines()[0][:LONG_VALUE_CHARS])}…"
            details.append(
                f"<!-- row-detail: {position} -->\n\n"
                f"{rewrite_text(text, context, head)}\n\n<!-- /row-detail -->"
            )
        else:
            cell = link if link is not None else _escape_cell(text)
        rows.append(f"| {_escape_cell(name)} | {cell} |")
    table = "\n".join(
        ["<!-- table: plain -->", "| 項目 | 値 |", "| --- | --- |", *rows, "<!-- /table -->"]
    )
    return "\n\n".join([table, *details])


def _date(value: Any) -> str | None:
    """文書の日時を `YYYY-MM-DD` にする。"""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value[:10]
    return None


class _Builder:
    """文書の値をスキーマに沿って Markdown の塊の並びにする。"""

    def __init__(self, document: IndexedDocument, context: RenderContext, scope: str) -> None:
        self.kind = document.kind
        self.data = document.data
        self.context = context
        self.scope = scope
        self.updated = _date(document.updated) or NO_DATE
        self.blocks: list[str] = []

    def head(self, title: str) -> DiagramHead:
        """図の部品の定義に入れる題名・範囲・更新日を作る。"""
        return DiagramHead(title=title, scope=self.scope, updated=self.updated)

    def heading(self, text: str, level: int) -> None:
        """見出しを配置する（深さは `MAX_HEADING_LEVEL` で止める）。"""
        self.blocks.append(f"{'#' * min(level, MAX_HEADING_LEVEL)} {text}")

    def text(self, value: Any, title: str) -> str:
        """スカラーを、参照のリンクか本文の書き換えにかけた文字列にする。"""
        text = _scalar(value)
        if isinstance(value, str):
            link = link_reference(value, self.context)
            if link is not None:
                return link
            return rewrite_text(text, self.context, self.head(title))
        return text

    def object(
        self,
        data: Mapping[str, Any],
        schema: Mapping[str, Any],
        path: str,
        level: int,
        skip: Sequence[str] = (),
    ) -> None:
        """オブジェクトの子を、スキーマの `properties` の順に組み立てる。"""
        properties: Mapping[str, Any] = schema.get("properties") or {}
        keys = [
            key
            for key in [*properties, *(key for key in data if key not in properties)]
            if key in data
            and key not in skip
            and not _is_empty(data[key])
            and not _is_hidden(properties.get(key))
        ]

        def sub_of(key: str) -> Mapping[str, Any]:
            sub = properties.get(key)
            return sub if isinstance(sub, Mapping) else {}

        def is_plain_scalar(key: str) -> bool:
            sub = sub_of(key)
            return (
                _is_scalar(data[key])
                and not sub.get("x-heading")
                and not sub.get("x-shape")
                and key not in TEST_FILE_KEYS
                and not key.endswith(EXAMPLE_SUFFIX)
            )

        index = 0
        while index < len(keys):
            key = keys[index]
            # 見出しも表し方も持たないスカラーの並び: `ATTRIBUTE_MIN` 以上なら属性の表にまとめる
            run = 0
            while index + run < len(keys) and is_plain_scalar(keys[index + run]):
                run += 1
            if run >= ATTRIBUTE_MIN:
                pairs = [
                    (str(sub_of(name).get("title") or name), data[name])
                    for name in keys[index : index + run]
                ]
                self.blocks.append(render_attributes(pairs, self.context, self.head(self.scope)))
                index += run
                continue
            # リクエスト例・レスポンス例の並び: タブで切り替える
            if key.endswith(EXAMPLE_SUFFIX):
                end = index
                while end < len(keys) and keys[end].endswith(EXAMPLE_SUFFIX):
                    end += 1
                self.examples(data, keys[index:end], sub_of, level)
                index = end
                continue
            self.value(key, data[key], sub_of(key), f"{path}.{key}" if path else key, level)
            index += 1

    def examples(
        self,
        data: Mapping[str, Any],
        keys: Sequence[str],
        sub_of: Any,
        level: int,
    ) -> None:
        """例の値ごとに見出しと本文を配置し、`<!-- tabs -->` の範囲で囲む。"""
        self.blocks.append("<!-- tabs -->")
        for key in keys:
            title = str(sub_of(key).get("title") or key)
            self.heading(title, level)
            value = data[key]
            self.blocks.append(
                self.text(value, title) if _is_scalar(value) else _cell(value, self.context)
            )
        self.blocks.append("<!-- /tabs -->")

    def value(self, key: str, value: Any, sub: Mapping[str, Any], path: str, level: int) -> None:
        """値 1 つを `x-heading`・`x-shape` に沿って組み立てる。"""
        title = str(sub.get("title") or key)
        heading = sub.get("x-heading")
        shape = sub.get("x-shape")
        # 検討事項の並び: リンク先の決まる ID を先にリンクにしてから組み立てる
        if key == DECISIONS_KEY and isinstance(value, list):
            value = link_decisions(value, self.context)
        content_level = level
        if heading:
            self.heading(str(heading), level)
            content_level = level + 1
        if key in TEST_FILE_KEYS:
            self.test_files(title, value)
        elif shape == "diagram" and isinstance(value, Mapping):
            self.diagram(title, value, sub, path)
        elif shape == "sections" and isinstance(value, list | Mapping):
            self.sections(value, sub, path, content_level)
        elif shape == "attributes" and isinstance(value, Mapping):
            self.attributes(value, sub)
        elif shape == "list" and isinstance(value, list):
            self.bullets(value, title)
        elif shape == "table" and _is_rows(value):
            self.table(value, sub, path)
        else:
            self.plain(title, value, sub, path, content_level, labeled=not heading)

    def test_files(self, title: str, value: Any) -> None:
        """対応テストファイルを、引き先があればリンク、無ければ行内のコードの 1 列の閉じた表にする。"""
        paths = [str(item) for item in value] if isinstance(value, list) else [str(value)]
        cells = [link_reference(path, self.context) or f"`{path}`" for path in paths]
        lines = ["<!-- table: plain closed -->", f"| {title} |", "| --- |"]
        lines.extend(f"| {cell} |" for cell in cells)
        lines.append("<!-- /table -->")
        self.blocks.append("\n".join(lines))

    def table(self, rows: Sequence[Mapping[str, Any]], sub: Mapping[str, Any], path: str) -> None:
        """オブジェクトのリストを表にする。"""
        items = sub.get("items")
        table = render_table(
            rows,
            items if isinstance(items, Mapping) else {},
            table_key=f"{self.kind}:{path}",
            context=self.context,
        )
        if table:
            self.blocks.append(table)

    def bullets(self, values: Sequence[Any], title: str) -> None:
        """リストを箇条書きにする（文字列は参照のリンクか本文の書き換えにかける）。"""
        items = [
            self.text(item, title) if _is_scalar(item) else _cell(item, self.context)
            for item in values
            if not _is_empty(item)
        ]
        self.blocks.append("\n".join(f"- {item}" for item in items))

    def diagram(
        self, title: str, value: Mapping[str, Any], sub: Mapping[str, Any], path: str
    ) -> None:
        """図と、続けて同じ値の閉じた元データの表を配置する。"""
        kind: DiagramKind = sub.get("x-diagram", "flowchart")
        # ER 図の列を補う同じ文書のテーブル（ER 図以外は使用しない）
        tables = self.data.get(ER_TABLES_KEY) if isinstance(self.data, Mapping) else None
        self.blocks.append(render_diagram(value, kind, self.head(title), tables=_items(tables)))
        properties: Mapping[str, Any] = sub.get("properties") or {}
        for key, rows in value.items():
            if not _is_rows(rows):
                continue
            item_sub = properties.get(key, {})
            items = item_sub.get("items") if isinstance(item_sub, Mapping) else None
            present = {name for row in rows for name in row}
            self.blocks.append(
                render_table(
                    rows,
                    items if isinstance(items, Mapping) else {},
                    table_key=f"{self.kind}:{path}.{key}",
                    context=self.context,
                    closed=True,
                    first=next((name for name in LABEL_KEYS if name in present), None),
                    hidden=[name for name in DIAGRAM_HIDDEN_KEYS if name in present],
                )
            )

    def attributes(self, value: Mapping[str, Any], sub: Mapping[str, Any]) -> None:
        """子のスカラーを「項目 / 値」の表にする。"""
        properties: Mapping[str, Any] = sub.get("properties") or {}
        pairs = [
            (str((properties.get(key) or {}).get("title") or key), item)
            for key, item in value.items()
            if _is_scalar(item) and not _is_empty(item) and not _is_hidden(properties.get(key))
        ]
        if pairs:
            self.blocks.append(render_attributes(pairs, self.context, self.head(self.scope)))

    def sections(self, value: Any, sub: Mapping[str, Any], path: str, level: int) -> None:
        """要素・子を 1 つ深い見出しのセクションにする。"""
        if isinstance(value, list):
            items = sub.get("items") if isinstance(sub.get("items"), Mapping) else {}
            x_key = sub.get("x-key")
            for index, element in enumerate(value):
                label = element.get(x_key) if isinstance(element, Mapping) and x_key else None
                self.heading(str(label if label is not None else index + 1), level)
                child_path = f"{path}[{index}]"
                if isinstance(element, Mapping):
                    self.object(
                        element,
                        items,  # type: ignore[arg-type]
                        child_path,
                        level + 1,
                        skip=[x_key] if x_key else [],
                    )
                elif not _is_empty(element):
                    self.blocks.append(self.text(element, str(index + 1)))
            return
        properties: Mapping[str, Any] = sub.get("properties") or {}
        for key, child in value.items():
            if _is_empty(child) or _is_hidden(properties.get(key)):
                continue
            child_sub = properties.get(key, {})
            child_sub = child_sub if isinstance(child_sub, Mapping) else {}
            self.heading(str(child_sub.get("x-heading") or child_sub.get("title") or key), level)
            self.value(key, child, {**child_sub, "x-heading": None}, f"{path}.{key}", level + 1)

    def plain(
        self,
        title: str,
        value: Any,
        sub: Mapping[str, Any],
        path: str,
        level: int,
        *,
        labeled: bool,
    ) -> None:
        """`x-shape` が無い値を、種類ごとの既定の表し方で組み立てる。"""
        if _is_scalar(value):
            text = self.text(value, title)
            # 見出しの下の値: そのまま配置する
            if not labeled:
                self.blocks.append(text)
            # 複数行・ブロックで始まる値: ラベルを独立した行にし、値を次のブロックに配置する
            elif "\n" in text or text.startswith(("```", "<!--")):
                self.blocks.append(f"**{title}**")
                self.blocks.append(text)
            else:
                self.blocks.append(f"**{title}**: {text}")
            return
        if labeled:
            self.blocks.append(f"**{title}**")
        if isinstance(value, Mapping):
            self.object(value, sub, path, level)
        elif _is_rows(value):
            self.table(value, sub, path)
        else:
            self.bullets(value, title)


def _anchors(data: Any, schema: Any, found: dict[str, str]) -> dict[str, str]:
    """`x-key` を持つ `sections` の要素の `title` と見出しの組を集める。"""
    if not isinstance(schema, Mapping):
        return found
    if isinstance(data, Mapping):
        properties: Mapping[str, Any] = schema.get("properties") or {}
        for key, child in data.items():
            _anchors(child, properties.get(key), found)
    elif isinstance(data, list):
        x_key = schema.get("x-key") if schema.get("x-shape") == "sections" else None
        for element in data:
            if (
                x_key
                and isinstance(element, Mapping)
                and element.get("title")
                and element.get(x_key)
            ):
                found.setdefault(str(element["title"]), str(element[x_key]))
            _anchors(element, schema.get("items"), found)
    return found


def item_heading(data: Mapping[str, Any], schema: Mapping[str, Any], item: str) -> str | None:
    """文書の項目のパスが、スキーマ駆動の変換で見出しになる項目を指すとき、その見出しを返却する。"""
    value: Any = data
    sub: Any = schema
    heading: Any = None
    for step in ITEM_STEP.finditer(item):
        if not isinstance(sub, Mapping) or not isinstance(value, Mapping):
            return None
        properties: Mapping[str, Any] = sub.get("properties") or {}
        sub = properties.get(step["key"])
        value = value.get(step["key"])
        if not isinstance(sub, Mapping):
            return None
        label = step["label"]
        # `{キー}`: キーの `x-heading` がこの階層の見出し
        if label is None:
            heading = sub.get("x-heading")
            continue
        # `{キー}[{値}]`: `sections` の要素のうち `x-key` が値に該当する要素へ進み、その値が見出し
        x_key = sub.get("x-key")
        if sub.get("x-shape") != "sections" or not x_key or not isinstance(value, list):
            return None
        value = next(
            (e for e in value if isinstance(e, Mapping) and str(e.get(x_key)) == label), None
        )
        if value is None:
            return None
        sub = sub.get("items")
        heading = label
    return str(heading) if heading else None


def _first(data: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    """`keys` のうち最初に値を持つキーを返却する。"""
    return next((key for key in keys if not _is_empty(data.get(key))), None)


def schema_to_markdown(
    document: IndexedDocument, schema: Mapping[str, Any], context: RenderContext
) -> str:
    """YAML の文書をスキーマの `x-heading`・`x-shape`・`x-key`・`x-diagram`・`x-hidden`・`title` に沿って Markdown にする。"""
    data = document.data
    tables = data.get(ER_TABLES_KEY) if isinstance(data, Mapping) else None
    context = replace(
        context,
        anchors=_anchors(data, schema, {}),
        table_titles=er_table_titles(_items(tables)),
    )
    heading_key = _first(data, HEADING_KEYS)
    lead_key = _first(data, LEAD_KEYS)
    name = str(data[heading_key]) if heading_key else str(document.metadata["name"])
    builder = _Builder(document, context, name)
    builder.blocks.append(f"# {name}")
    if lead_key:
        builder.blocks.append(builder.text(data[lead_key], name))
    used = [key for key in (heading_key, lead_key) if key]
    builder.object(data, schema, "", FIRST_HEADING_LEVEL, skip=used)
    return "\n\n".join(block for block in builder.blocks if block) + "\n"
