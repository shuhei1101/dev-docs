"""説明の Markdown。"""

from __future__ import annotations

from dev_docs.features.describe.types import KindSchemaResult, SourceGuideResult, SourceListResult


def _cell(text: str) -> str:
    """表のセルの文字列にする。"""
    return text.replace("|", "\\|").replace("\n", "<br>")


def _place(result: SourceListResult) -> str:
    """作業場所の行を作る。"""
    workplace = result.workplace
    if workplace.source_id is None:
        return f"作業場所: {workplace.cwd}（どの配信元の中でもありません）"
    kind = "ワークツリー" if workplace.worktree is not None else "クローン本体"
    return f"作業場所: {workplace.cwd}（{workplace.source_id} の{kind}）"


def render_describe_markdown(
    result: SourceListResult | SourceGuideResult | KindSchemaResult,
) -> str:
    """`format: markdown` の本文を作る。"""
    if isinstance(result, SourceListResult):
        lines = [_place(result), "", "| source | 権限 | description |", "| --- | --- | --- |"]
        for item in result.sources:
            access = f"{item.access}（作業中）" if item.current else item.access
            lines.append(f"| {_cell(item.source_id)} | {access} | {_cell(item.description)} |")
        return "\n".join(lines) + "\n"
    if isinstance(result, SourceGuideResult):
        lines = [result.instructions, "", "| kind | description |", "| --- | --- |"]
        lines.extend(f"| {_cell(kind.id)} | {_cell(kind.description)} |" for kind in result.kinds)
        return "\n".join(lines) + "\n"
    lines = []
    if result.metadata:
        lines = ["| 共通のキー | 列名 |", "| --- | --- |"]
        lines.extend(
            f"| {_cell(key)} | {_cell(column)} |" for key, column in result.metadata.items()
        )
        lines.append("")
    lines.append(f"```yaml\n{result.schema_text.rstrip(chr(10))}\n```")
    return "\n".join(lines) + "\n"
