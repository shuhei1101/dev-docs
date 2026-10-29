"""管理の MCP の `status`・`reload`・`check_project`・`try_convert` の中身。"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from dev_docs.features.access.types import Target
from dev_docs.features.admin.types import (
    SYNC_ITEMS_LIMIT,
    CandidateSource,
    CheckProjectRequest,
    CheckProjectResult,
    CheckSync,
    NotServedItem,
    ReloadResult,
    ScriptErrorItem,
    ServerStatus,
    SourceState,
    SyncCounts,
    SyncItem,
    TerminalState,
    TryConvertRequest,
    TryConvertResult,
    VersionState,
)
from dev_docs.features.convert.service import ConvertService
from dev_docs.features.documents.loader import collect_files
from dev_docs.features.documents.store import check_sync
from dev_docs.features.settings.query import (
    SETTINGS_VERSION,
    listen_port,
    load_terminal_config,
)
from dev_docs.features.sources.service import assemble_source
from dev_docs.features.sources.types import SOURCE_CONFIG_VERSION
from dev_docs.shared.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConvertScriptError,
    DocumentNotFoundError,
    ValidationFailedError,
    Violation,
)
from dev_docs.shared.paths import normalize_path
from dev_docs.shared.version import RUNNING_VERSION
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

CONFIG_FILE = "dev-docs.yaml"
DOCUMENT_SEPARATOR = "\n\n---\n\n"
BUILTIN_CONVERTER = "builtin:markdown"


def version_state(mine: str, current: str) -> VersionState:
    """設定のバージョンを dev-docs が読めるバージョンと比べる。"""
    left, right = int(mine), int(current)
    if left == right:
        return "current"
    return "old" if left < right else "newer"


def _source_states(handlers: Handlers) -> list[SourceState]:
    """登録簿の状態を配信元の状態の行にする。"""
    states: list[SourceState] = []
    for status in handlers.registry.statuses():
        # 配信中だけ、設定のバージョンの新旧と索引の同期の件数を持つ
        if status.status == "serving":
            source = handlers.registry.get(status.id)
            config_version = source.config.version
            states.append(
                SourceState(
                    id=status.id,
                    status="serving",
                    errors=[],
                    config_version=config_version,
                    version_state=version_state(config_version, SOURCE_CONFIG_VERSION),
                    sync=SyncCounts.of(check_sync(handlers.store, source)),
                )
            )
            continue
        errors = [f"{item.path}: {item.rule}" for item in status.errors]
        states.append(
            SourceState(
                id=status.id,
                status=status.status,
                errors=errors,
                config_version=None,
                version_state=None,
                sync=None,
            )
        )
    return states


def get_status(handlers: Handlers, *, env: Mapping[str, str]) -> ServerStatus:
    """待ち受けのアドレス・バージョン・配信元ごとの状態を返す。"""
    port = listen_port(handlers.terminal, env)
    return ServerStatus(
        address=f"http://{handlers.terminal.bind}:{port}/",
        version=RUNNING_VERSION,
        pid=os.getpid(),
        terminal=TerminalState(
            file=str(handlers.terminal.file),
            version_state=version_state(handlers.terminal.version, SETTINGS_VERSION),
        ),
        sources=_source_states(handlers),
    )


def reload_config(handlers: Handlers) -> ReloadResult:
    """端末の設定と配信元の設定を読み直し、前後の差を返す。"""
    # 端末の設定の保存と同じロックの中で、一度に 1 つだけ読み直す
    with handlers.settings_lock:
        before = _serving_ids(handlers)
        terminal = load_terminal_config(handlers.terminal.file)
        statuses = handlers.reload_sources(terminal)
        after = [status.id for status in statuses if status.status == "serving"]
        result = ReloadResult(
            added=[source_id for source_id in after if source_id not in before],
            removed=[source_id for source_id in before if source_id not in after],
            not_served=[
                NotServedItem(
                    id=status.id, errors=[f"{item.path}: {item.rule}" for item in status.errors]
                )
                for status in statuses
                if status.status == "not_served"
            ],
            sources=_source_states(handlers),
        )
    logger.info(
        "設定を読み直した（追加 %s・削除 %s・配信していない %s）",
        len(result.added),
        len(result.removed),
        len(result.not_served),
    )
    return result


def _serving_ids(handlers: Handlers) -> list[str]:
    """配信中の配信元の ID を `sources[]` の順に返す。"""
    return [status.id for status in handlers.registry.statuses() if status.status == "serving"]


def _load_candidate(path: str, *, config: str | None) -> CandidateSource:
    """パスか書く前の設定の文字列から、端末の設定によらず配信元を組み立てる。"""
    target = normalize_path(path)
    # `.yaml` で終わるパスは設定のファイル、それ以外は配信元のフォルダ
    root, config_file = (
        (target.parent, target) if target.suffix == ".yaml" else (target, target / CONFIG_FILE)
    )
    if config is not None:
        text = config
    elif not config_file.is_file():
        raise ConfigNotFoundError(
            message=f"{config_file}: dev-docs.yaml がありません",
            path=str(config_file),
            next_steps=["/dev-docs:setup で配信元を追加してください"],
        )
    else:
        text = config_file.read_text(encoding="utf-8")
    try:
        value = load_yaml(text, file=str(config_file))
    except YamlLoadError as error:
        raise ConfigParseError(message=str(error), line=error.line, column=error.column) from error
    config_version = (
        str(value["version"]) if isinstance(value, dict) and "version" in value else None
    )
    # 書く前の設定は、使い捨てのフォルダに書いて読む（相対パスは配信元のフォルダから解く）
    with tempfile.TemporaryDirectory() as directory:
        file = config_file
        if config is not None:
            file = Path(directory) / CONFIG_FILE
            file.write_text(text, encoding="utf-8")
        served, loaded, violations = assemble_source(
            [file], source_id=None, scope_read=[], scope_write=None, root_override=root
        )
    if loaded is None:
        return CandidateSource(
            root=root,
            config_version=config_version,
            violations=violations,
            script_violations=[],
            source=None,
        )
    # スクリプトの確かめの失敗は、スクリプトのコマンドを違反の場所にして持つ
    script_violations = [
        Violation(path=_command(loaded, violation.path), rule=violation.rule)
        for violation in violations
    ]
    return CandidateSource(
        root=root,
        config_version=config_version,
        violations=[],
        script_violations=script_violations,
        source=served,
    )


def _command(config: object, key_path: str) -> str:
    """`converters[0]` のような場所から、スクリプトのコマンドを空白でつないだ文字列にする。"""
    table, _, rest = key_path.partition("[")
    rows = getattr(config, table, [])
    return " ".join(rows[int(rest.rstrip("]"))].run)


def _registered_id(handlers: Handlers, root: Path) -> str | None:
    """端末の設定に、`config` の先頭のファイルのフォルダが同じ行があれば、その ID を返す。"""
    statuses = handlers.registry.statuses()
    for index, entry in enumerate(handlers.terminal.sources):
        if normalize_path(entry.config[0]).parent == root:
            if entry.id:
                return entry.id
            return statuses[index].id if index < len(statuses) else None
    return None


def check_project(request: CheckProjectRequest, *, handlers: Handlers) -> CheckProjectResult:
    """端末の設定に無い配信元も含め、設定・スクリプト・索引の同期を検査する。"""
    candidate = _load_candidate(request.path, config=request.config)
    registered_id = _registered_id(handlers, candidate.root)
    state = (
        version_state(candidate.config_version, SOURCE_CONFIG_VERSION)
        if candidate.config_version is not None and candidate.config_version.isdecimal()
        else None
    )
    result = CheckProjectResult(
        path=str(candidate.root),
        registered_id=registered_id,
        config_version=candidate.config_version,
        version_state=state,
        violations=candidate.violations,
        missing_paths=[],
        script_errors=[
            ScriptErrorItem(script=item.path, reason=item.rule)
            for item in candidate.script_violations
        ],
        sync=None,
    )
    # 配信元を組み立てられなかった（違反かスクリプトの失敗）ときは、ここまで
    source = candidate.source
    if source is None:
        return result
    missing_paths = [
        pattern
        for table in source.config.documents
        for pattern in table.paths
        if not collect_files(source.root, replace(table, paths=[pattern]))
    ]
    report = check_sync(handlers.store, source)
    entries = (
        ("missing_refs", report.missing_refs),
        ("unindexed_files", report.unindexed_files),
        ("missing_body_files", report.missing_body_files),
    )
    items = [SyncItem(kind=kind, path=path) for kind, paths in entries for path in paths]  # type: ignore[arg-type]
    counts = SyncCounts.of(report)
    return CheckProjectResult(
        path=result.path,
        registered_id=registered_id,
        config_version=candidate.config_version,
        version_state=state,
        violations=[],
        missing_paths=missing_paths,
        script_errors=[],
        sync=CheckSync(
            missing_refs=counts.missing_refs,
            unindexed_files=counts.unindexed_files,
            missing_body_files=counts.missing_body_files,
            items=items[:SYNC_ITEMS_LIMIT],
        ),
    )


def try_convert(request: TryConvertRequest, *, handlers: Handlers) -> TryConvertResult:
    """指した配信元のファイルを、配信元の変換で Markdown にする。"""
    candidate = _load_candidate(request.path, config=request.config)
    source = candidate.source
    if source is None:
        count = len(candidate.violations) + len(candidate.script_violations)
        raise ValidationFailedError(
            message=f"{candidate.root}: 配信元の設定に違反が {count} 件あります",
            violations=[*candidate.violations, *candidate.script_violations],
            next_steps=["check_project で違反を確かめてください"],
        )
    # 配信元の外を指すファイルは断る
    file = normalize_path(candidate.root / request.file)
    if not file.is_relative_to(candidate.root):
        raise DocumentNotFoundError(
            message=f"{request.file}: 配信元の外です", missing=[request.file]
        )
    # ファイルが範囲に当たり、除外に当たらない最初の文書の行を引く
    relative = file.relative_to(candidate.root).as_posix()
    table = next(
        (row for row in source.config.documents if row.enabled and row.matches(relative)), None
    )
    not_matched = DocumentNotFoundError(
        message=f"{request.file}: 文書の種類の範囲に当たる文書がありません", missing=[request.file]
    )
    target = Target(source, candidate.root, None, None, "read")
    if table is None:
        # 当たる行が無ければ、本文のファイルが `file` の文書を持つ最初の行を引く
        table = next(
            (
                row
                for row in source.config.documents
                if row.enabled
                and row.body_file is not None
                and any(
                    document.body_path == relative
                    for document in handlers.store.load(target, kinds=[row.id]).documents
                )
            ),
            None,
        )
    if table is None:
        raise not_matched
    documents = [
        document
        for document in handlers.store.load(target, kinds=[table.id]).documents
        if relative in (document.path, document.body_path)
    ]
    if not documents:
        raise not_matched
    # 配信中の変換の控えを汚さないよう、使い捨てのフォルダを控えの場所にして変換する
    with tempfile.TemporaryDirectory() as directory:
        converter = ConvertService(
            Path(directory), handlers.store, handlers.terminal.script_timeout_sec
        )
        converted = [converter.convert(target, document) for document in documents]
    for item in converted:
        if item.failure is not None:
            raise ConvertScriptError(
                message=f"{item.failure.reason}: {item.failure.detail}",
                script=item.failure.script or "",
            )
    used = BUILTIN_CONVERTER
    if table.converter is not None:
        used = source.script("converters", table.converter).run[-1]
    return TryConvertResult(
        kind=table.id,
        converter=used,
        markdown=DOCUMENT_SEPARATOR.join(item.markdown for item in converted),
    )
