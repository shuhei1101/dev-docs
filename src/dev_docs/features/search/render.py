"""検索の結果の Markdown。"""

from __future__ import annotations

from typing import Any

from dev_docs.features.search.types import SearchItem, SearchResult, Snippet

COLUMN_TITLES = {"@chars": "chars"}
BODY_FIELD = "body"
ARRAY_JOINER = ", "
SNIPPET_SEPARATOR = "--"
HIT_MARK = ":"
CONTEXT_MARK = "-"


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


def _snippet_lines(snippets: list[Snippet]) -> list[str]:
    """抜粋を grep の `-n` と同じ書式の行にする（当たった行は `:`、前後の行は `-`、抜粋の間は `--`）。"""
    lines: list[str] = []
    for index, snippet in enumerate(snippets):
        if index > 0:
            lines.append(SNIPPET_SEPARATOR)
        lines.extend(
            f"{line.line}{HIT_MARK if line.hit else CONTEXT_MARK}{line.text}"
            for line in snippet.lines
        )
    return lines


def _full(item: SearchItem) -> list[str]:
    """`view: full` の文書 1 件を、`<document>` で包んだ項目の箇条書きと本文にする。"""
    attributes = f' path="{item.path}" scope="{item.scope}"' if item.path else ""
    lines = [f"<document{attributes}>", f"- id: {item.id}"]
    if item.source:
        lines.append(f"- source: {item.source}")
    body = item.values.get(BODY_FIELD)
    lines.extend(
        f"- {_title(name)}: {_cell(value)}"
        for name, value in item.values.items()
        if name != BODY_FIELD
    )
    if item.snippets:
        lines.append("")
        lines.extend(_snippet_lines(item.snippets))
    if isinstance(body, str):
        lines.append("")
        lines.append(body.rstrip("\n"))
    lines.append("</document>")
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
