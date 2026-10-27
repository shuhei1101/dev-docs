"""検索の結果の Markdown。"""

from __future__ import annotations

from typing import Any

from dev_docs.features.search.types import SearchItem, SearchResult
from dev_docs.features.seen.types import SEEN_MARK

COLUMN_TITLES = {"@chars": "chars"}
BODY_FIELD = "body"
ARRAY_JOINER = ", "


def _title(name: str) -> str:
    """表の列名にする（`@chars` は `chars`）。"""
    return COLUMN_TITLES.get(name, name.removeprefix("@"))


def _cell(value: Any) -> str:
    """表のセルの文字列にする。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return ARRAY_JOINER.join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _table(result: SearchResult) -> list[str]:
    """項目を列にした表を作る。"""
    has_source = any(item.source for item in result.items)
    columns = ["id", *(["source"] if has_source else [])]
    for item in result.items:
        columns.extend(name for name in item.values if name not in columns)
    lines = [
        f"| {' | '.join(_title(name) for name in columns)} |",
        f"| {' | '.join('---' for _ in columns)} |",
    ]
    for item in result.items:
        cells = {"id": item.id, "source": item.source, **item.values}
        lines.append(f"| {' | '.join(_cell(cells.get(name)) for name in columns)} |")
    return lines


def _full(item: SearchItem) -> list[str]:
    """`view: full` の文書 1 件を、項目の箇条書きと本文にする。"""
    heading = f"## {item.id}" + (f"（{item.source}）" if item.source else "")
    lines = [heading, ""]
    body = item.values.get(BODY_FIELD)
    lines.extend(
        f"- {_title(name)}: {_cell(value)}"
        for name, value in item.values.items()
        if name != BODY_FIELD
    )
    if item.snippets:
        lines.append("")
        lines.extend(snippet for snippet in item.snippets)
    if isinstance(body, str):
        lines.append("")
        if body == SEEN_MARK or item.markdown:
            lines.append(body)
        else:
            lines.extend(["```yaml", body.rstrip("\n"), "```"])
    return lines


def render_search_markdown(result: SearchResult, *, source_label: str) -> str:
    """`format: markdown` の本文を作る。"""
    head = f"{source_label}: 該当 {result.total_count} 件・返した {result.returned} 件"
    if result.per_source:
        counts = "・".join(f"{name} {count} 件" for name, count in result.per_source.items())
        head += f"（{counts}）"
    lines = [head, ""]
    if result.groups:
        lines.extend(["| 値 | 件数 |", "| --- | --- |"])
        lines.extend(f"| {_cell(group.value)} | {group.count} |" for group in result.groups)
        lines.append("")
    if result.items:
        if result.view == "full":
            for item in result.items:
                lines.extend(_full(item))
                lines.append("")
        else:
            lines.extend(_table(result))
            lines.append("")
    lines.extend(f"> {note}" for note in result.notes)
    if result.next_cursor:
        lines.append(f"続き: cursor={result.next_cursor}")
    return "\n".join(lines).rstrip("\n") + "\n"
