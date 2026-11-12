"""管理の MCP の `format: markdown` の応答の文。"""

from __future__ import annotations

from dev_docs.features.admin.types import ServerStatus, SourceState

TABLE_HEADER = ("| source | 状態 |", "| --- | --- |")
UNREACHABLE_LINE = "配信元: project-index につながらないため取得できません"


def _source_row(state: SourceState) -> str:
    """配信元の状態を表の 1 行にする。"""
    status: str = state.status
    if state.status == "not_served":
        status = f"{state.status}（{'、'.join(state.errors)}）"
    return f"| {state.id} | {status} |"


def render_status(status: ServerStatus) -> str:
    """サーバーの状態を Markdown にする。"""
    connection = (
        "つながっている"
        if status.project_index.reachable
        else f"つながらない: {status.project_index.error}"
    )
    lines = [
        f"{status.address} dev-docs {status.version}（pid {status.pid}）",
        f"端末の設定: {status.terminal.file}（{status.terminal.version_state}）",
        f"project-index: {status.project_index.address}（{connection}）",
    ]
    if not status.project_index.reachable:
        lines.append(UNREACHABLE_LINE)
    elif status.sources:
        lines.extend([*TABLE_HEADER, *(_source_row(state) for state in status.sources)])
    else:
        lines.append("配信元: なし")
    if status.leftover_sources:
        lines.append(
            f"端末の設定に残った sources: {'・'.join(status.leftover_sources)}"
            "（project-index の端末の設定へ追加してください）"
        )
    return "\n".join(lines)
