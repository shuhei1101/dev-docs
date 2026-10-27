"""スキーマ駆動の Markdown への変換。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from dev_docs.features.convert.diagrams import render_diagram
from dev_docs.features.convert.types import DiagramKind
from dev_docs.features.documents.types import Document

MAX_HEADING_LEVEL = 6
FIRST_HEADING_LEVEL = 2
SKIPPED_KEYS = ("name", "description")
CELL_JOINER = "・"


def _is_empty(value: Any) -> bool:
    """値が空（組み立てずに飛ばす）かを返す。"""
    return value is None or value == "" or value == [] or value == {}


def _scalar(value: Any) -> str:
    """スカラーを文字列にする。"""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _is_scalar(value: Any) -> bool:
    """辞書でも配列でもない値かを返す。"""
    return not isinstance(value, Mapping | list)


def _is_rows(value: Any) -> bool:
    """辞書だけの配列かを返す。"""
    return isinstance(value, list) and bool(value) and all(isinstance(v, Mapping) for v in value)


def _cell(value: Any) -> str:
    """表のセルの文字列にする。"""
    if value is None:
        return ""
    if isinstance(value, list):
        if all(_is_scalar(item) for item in value):
            return CELL_JOINER.join(_cell(item) for item in value)
        return f"{len(value)} 件"
    if isinstance(value, Mapping):
        return f"{len(value)} 件"
    return _scalar(value).replace("\r\n", "\n").replace("|", "\\|").replace("\n", "<br>")


def render_table(
    rows: Sequence[Mapping[str, Any]], item_schema: Mapping[str, Any], *, table_key: str
) -> str:
    """オブジェクトのリストを、mdmark の表のマーカーつきの Markdown の表にする。"""
    properties: Mapping[str, Any] = item_schema.get("properties") or {}
    keys = list(properties)
    keys.extend(key for row in rows for key in row if key not in keys)
    keys = list(dict.fromkeys(keys))
    columns = [key for key in keys if any(not _is_empty(row.get(key)) for row in rows)]
    if not columns:
        return ""
    titles = [str(properties.get(key, {}).get("title") or key) for key in columns]
    lines = [
        f"<!-- dev-docs-table: {table_key} -->",
        "<!-- table: data -->",
        f"| {' | '.join(titles)} |",
        f"| {' | '.join('---' for _ in columns)} |",
    ]
    lines.extend(f"| {' | '.join(_cell(row.get(key)) for key in columns)} |" for row in rows)
    lines.append("<!-- /table -->")
    return "\n".join(lines)


class _Builder:
    """文書の値をスキーマに沿って Markdown の塊の並びにする。"""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.blocks: list[str] = []

    def heading(self, text: str, level: int) -> None:
        """見出しを置く（深さは `MAX_HEADING_LEVEL` で止める）。"""
        self.blocks.append(f"{'#' * min(level, MAX_HEADING_LEVEL)} {text}")

    def object(
        self, data: Mapping[str, Any], schema: Mapping[str, Any], path: str, level: int
    ) -> None:
        """オブジェクトの子を、スキーマの `properties` の順に組み立てる。"""
        properties: Mapping[str, Any] = schema.get("properties") or {}
        keys = [*properties, *(key for key in data if key not in properties)]
        for key in keys:
            if key not in data or _is_empty(data[key]):
                continue
            if not path and key in SKIPPED_KEYS:
                continue
            sub = properties.get(key)
            self.value(
                key,
                data[key],
                sub if isinstance(sub, Mapping) else {},
                f"{path}.{key}" if path else key,
                level,
            )

    def value(self, key: str, value: Any, sub: Mapping[str, Any], path: str, level: int) -> None:
        """値 1 つを `x-heading`・`x-shape` に沿って組み立てる。"""
        title = str(sub.get("title") or key)
        heading = sub.get("x-heading")
        shape = sub.get("x-shape")
        content_level = level
        if heading:
            self.heading(str(heading), level)
            content_level = level + 1
        if shape == "diagram" and isinstance(value, Mapping):
            self.diagram(value, sub, path)
        elif shape == "sections" and isinstance(value, list | Mapping):
            self.sections(value, sub, path, content_level)
        elif shape == "attributes" and isinstance(value, Mapping):
            self.attributes(value, sub)
        elif shape == "list" and isinstance(value, list):
            self.bullets(value)
        elif shape == "table" and _is_rows(value):
            self.table(value, sub, path)
        else:
            self.plain(title, value, sub, path, content_level, labeled=not heading)

    def table(self, rows: Sequence[Mapping[str, Any]], sub: Mapping[str, Any], path: str) -> None:
        """オブジェクトのリストを表にする。"""
        items = sub.get("items")
        table = render_table(
            rows, items if isinstance(items, Mapping) else {}, table_key=f"{self.kind}:{path}"
        )
        if table:
            self.blocks.append(table)

    def bullets(self, values: Sequence[Any]) -> None:
        """リストを箇条書きにする。"""
        self.blocks.append("\n".join(f"- {_cell(item)}" for item in values if not _is_empty(item)))

    def diagram(self, value: Mapping[str, Any], sub: Mapping[str, Any], path: str) -> None:
        """Mermaid の図と、続けて同じ値の表を置く。"""
        kind: DiagramKind = sub.get("x-diagram", "flowchart")
        self.blocks.append(f"```mermaid\n{render_diagram(value, kind)}\n```")
        properties: Mapping[str, Any] = sub.get("properties") or {}
        for key, rows in value.items():
            if _is_rows(rows):
                item_sub = properties.get(key, {})
                items = item_sub.get("items") if isinstance(item_sub, Mapping) else None
                self.blocks.append(
                    render_table(
                        rows,
                        items if isinstance(items, Mapping) else {},
                        table_key=f"{self.kind}:{path}.{key}",
                    )
                )

    def attributes(self, value: Mapping[str, Any], sub: Mapping[str, Any]) -> None:
        """子のスカラーを `> {title}: {値}` の行にする。"""
        properties: Mapping[str, Any] = sub.get("properties") or {}
        lines = [
            f"> {properties.get(key, {}).get('title') or key}: {_cell(item)}"
            for key, item in value.items()
            if _is_scalar(item) and not _is_empty(item)
        ]
        if lines:
            self.blocks.append("<br>\n".join(lines))

    def sections(self, value: Any, sub: Mapping[str, Any], path: str, level: int) -> None:
        """要素・子を 1 つ深い見出しの節にする。"""
        if isinstance(value, list):
            items = sub.get("items") if isinstance(sub.get("items"), Mapping) else {}
            x_key = sub.get("x-key")
            for index, element in enumerate(value):
                label = element.get(x_key) if isinstance(element, Mapping) and x_key else None
                self.heading(str(label if label is not None else index + 1), level)
                child_path = f"{path}[{index}]"
                if isinstance(element, Mapping):
                    skip = {x_key} if x_key else set()
                    self.object(
                        {k: v for k, v in element.items() if k not in skip},
                        items,  # type: ignore[arg-type]
                        child_path,
                        level + 1,
                    )
                elif not _is_empty(element):
                    self.blocks.append(_cell(element))
            return
        properties: Mapping[str, Any] = sub.get("properties") or {}
        for key, child in value.items():
            if _is_empty(child):
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
        """`x-shape` が無い値を、種類ごとの既定の形で組み立てる。"""
        if _is_scalar(value):
            text = _scalar(value)
            self.blocks.append(f"**{title}**: {text}" if labeled else text)
        elif isinstance(value, Mapping):
            if labeled:
                self.blocks.append(f"**{title}**:")
            self.object(value, sub, path, level)
        elif _is_rows(value):
            if labeled:
                self.blocks.append(f"**{title}**:")
            self.table(value, sub, path)
        else:
            if labeled:
                self.blocks.append(f"**{title}**:")
            self.bullets(value)


def schema_to_markdown(document: Document, schema: Mapping[str, Any]) -> str:
    """YAML の文書をスキーマの `x-heading`・`x-shape`・`x-key`・`x-diagram`・`title` に沿って Markdown にする。"""
    data = document.data
    name = data.get("name") or document.metadata.get("name") or data.get("id") or document.id
    builder = _Builder(document.kind)
    builder.blocks.append(f"# {name}")
    description = data.get("description") or document.metadata.get("description")
    if description:
        builder.blocks.append(_scalar(description))
    builder.object(data, schema, "", FIRST_HEADING_LEVEL)
    return "\n\n".join(block for block in builder.blocks if block) + "\n"
