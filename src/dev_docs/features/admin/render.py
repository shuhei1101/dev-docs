"""管理の MCP の `format: markdown` の応答の文。"""

from __future__ import annotations

from dev_docs.features.admin.types import (
    CheckProjectResult,
    ReloadResult,
    ServerStatus,
    SourceState,
)

TABLE_HEADER = ("| source | 状態 | 設定のバージョン | 索引の同期 |", "| --- | --- | --- | --- |")
SYNC_LABELS = {
    "missing_refs": "metadata の列の欠け",
    "unindexed_files": "管理用の YAML に無いファイル",
    "missing_body_files": "ファイルが無い行",
}


def _source_row(state: SourceState) -> str:
    """配信元の状態を表の 1 行にする。"""
    status: str = state.status
    if state.status == "not_served":
        status = f"{state.status}（{'、'.join(state.errors)}）"
    version = (
        "-" if state.config_version is None else f"{state.config_version}（{state.version_state}）"
    )
    sync = "-"
    if state.sync is not None:
        sync = str(
            state.sync.missing_refs + state.sync.unindexed_files + state.sync.missing_body_files
        )
    return f"| {state.id} | {status} | {version} | {sync} |"


def render_status(status: ServerStatus) -> str:
    """サーバーの状態を Markdown にする。"""
    lines = [
        f"{status.address} dev-docs {status.version}（pid {status.pid}）",
        f"端末の設定: {status.terminal.file}（{status.terminal.version_state}）",
    ]
    if status.sources:
        lines.extend([*TABLE_HEADER, *(_source_row(state) for state in status.sources)])
    else:
        lines.append("配信元: なし")
    return "\n".join(lines)


def render_reload(result: ReloadResult) -> str:
    """読み直しの結果を Markdown にする。"""
    not_served = "、".join(f"{item.id}（{'、'.join(item.errors)}）" for item in result.not_served)
    lines = [
        f"追加: {'、'.join(result.added) or 'なし'}",
        f"削除: {'、'.join(result.removed) or 'なし'}",
        f"配信していない: {not_served or 'なし'}",
    ]
    if result.sources:
        lines.extend([*TABLE_HEADER, *(_source_row(state) for state in result.sources)])
    return "\n".join(lines)


def render_check(result: CheckProjectResult) -> str:
    """配信元の検査の結果を Markdown にする。"""
    registered = f"登録済み: {result.registered_id}" if result.registered_id else "未登録"
    version = (
        "-"
        if result.config_version is None
        else f"{result.config_version}（{result.version_state}）"
    )
    lines = [f"{result.path}（{registered}）", f"設定のバージョン: {version}"]
    if result.violations:
        lines.append(f"違反: {len(result.violations)} 件")
        lines.extend(f"- {item.path}: {item.rule}" for item in result.violations)
    else:
        lines.append("違反: なし")
    if result.missing_paths:
        lines.append(f"無いパス: {len(result.missing_paths)} 件")
        lines.extend(f"- {path}" for path in result.missing_paths)
    if result.script_errors:
        lines.append(f"スクリプトの失敗: {len(result.script_errors)} 件")
        lines.extend(f"- {item.script}: {item.reason}" for item in result.script_errors)
    if result.sync is not None:
        counts = {
            "missing_refs": result.sync.missing_refs,
            "unindexed_files": result.sync.unindexed_files,
            "missing_body_files": result.sync.missing_body_files,
        }
        gaps = [f"{SYNC_LABELS[kind]} {count} 件" for kind, count in counts.items() if count]
        lines.append(f"索引の同期: {'、'.join(gaps) if gaps else 'ずれなし'}")
        lines.extend(f"- {item.kind}: {item.path}" for item in result.sync.items)
        if len(result.sync.items) < sum(counts.values()):
            lines.append(f"（先頭 {len(result.sync.items)} 件）")
    return "\n".join(lines)
