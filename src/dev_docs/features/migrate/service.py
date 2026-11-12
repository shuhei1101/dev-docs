"""`dev-docs migrate` の対象の決定・手順の一覧・適用。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from dev_docs.features.admin.service import version_state
from dev_docs.features.migrate.steps import apply_step, load_steps
from dev_docs.features.migrate.types import (
    BACKUP_FORMAT,
    BACKUP_TIME_FORMAT,
    ConfigNewerError,
    DestructiveStepBlockedError,
    MigrationConfigInvalidError,
    MigrationFailedError,
    MigrationOutcome,
    MigrationStep,
    MigrationTarget,
    ProjectIndexUnreachableMigrationError,
)
from dev_docs.features.settings.query import (
    SETTINGS_VERSION,
    config_path,
    validate_terminal_config,
)
from dev_docs.integrations.project_index.types import AddSourceResult
from dev_docs.shared.errors import (
    ProjectIndexRejectedError,
    ProjectIndexResponseError,
    ProjectIndexUnreachableError,
)
from dev_docs.shared.files import replace_file
from dev_docs.shared.hashing import content_hash
from dev_docs.shared.yaml_io import YamlLoadError, dump_roundtrip, load_roundtrip, load_yaml

logger = logging.getLogger(__name__)

PROJECT_INDEX_KEY = "project_index"
SOURCES_KEY = "sources"


def resolve_target(*, env: Mapping[str, str]) -> MigrationTarget:
    """移し替える端末の設定を決める。"""
    return MigrationTarget(kind="settings", file=config_path(env), current=SETTINGS_VERSION)


def plan_migration(target: MigrationTarget) -> tuple[CommentedMap, list[MigrationStep]]:
    """対象の `version` を読み込み、適用する手順を求める。"""
    try:
        data = load_roundtrip(target.file.read_text(encoding="utf-8"), file=str(target.file))
    except (OSError, YamlLoadError) as error:
        raise MigrationConfigInvalidError(f"{target.file}: {error}") from error
    version = str(data["version"]) if "version" in data else ""
    if not version.isdecimal():
        raise MigrationConfigInvalidError(
            f"{target.file}: version が整数の文字列で記載されていません"
        )
    state = version_state(version, target.current)
    # 新しすぎる設定は移し替えない
    if state == "newer":
        raise ConfigNewerError(
            f"{target.file}: 設定のバージョン {version} が dev-docs で読み込める {target.current}"
            " より新しい。dev-docs を更新してください"
        )
    if state == "current":
        return data, []
    return data, load_steps(target.kind, mine=version, current=target.current)


def _export_sources(
    data: CommentedMap,
    export_source: Callable[[Mapping[str, Any]], AddSourceResult],
    project_index: str,
) -> list[str]:
    """`sources` の行を 1 行ずつ project-index へ追加し、移行しなかった行の ID を返却する。"""
    rows = data.get(SOURCES_KEY)
    kept_rows: list[Any] = []
    kept: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        plain = _plain_row(row)
        try:
            result = export_source(plain)
        except ProjectIndexUnreachableError as error:
            raise ProjectIndexUnreachableMigrationError(error.address, error.reason) from error
        except (ProjectIndexResponseError, ProjectIndexRejectedError) as error:
            raise MigrationFailedError(str(error.message)) from error
        if result.added or result.same:
            continue
        kept_rows.append(row)
        kept.append(str(plain.get("id") or plain.get("config")))
    if kept_rows:
        data[SOURCES_KEY] = kept_rows
    elif SOURCES_KEY in data:
        del data[SOURCES_KEY]
    if PROJECT_INDEX_KEY not in data:
        data[PROJECT_INDEX_KEY] = project_index
    return kept


def _plain_row(row: Any) -> dict[str, Any]:
    """往復編集の行を、`config` を配列にした素の辞書にする。"""
    plain = load_yaml(dump_roundtrip(row)) if isinstance(row, CommentedMap) else dict(row)
    config = plain.get("config")
    if isinstance(config, str):
        plain["config"] = [config]
    return dict(plain)


def apply_migration(
    target: MigrationTarget,
    data: CommentedMap,
    steps: list[MigrationStep],
    *,
    allow_destructive: bool,
    export_source: Callable[[Mapping[str, Any]], AddSourceResult] | None,
    project_index: str,
    now: datetime,
) -> MigrationOutcome:
    """手順を全て適用して新しいスキーマで検証し、バックアップを取ってから 1 回だけ書き込む。"""
    # 破壊的な手順は、許されたときだけ適用する
    destructive = [step for step in steps if step.destructive]
    if destructive and not allow_destructive:
        lines = [f"{step.version}: {step.description}" for step in destructive]
        raise DestructiveStepBlockedError(
            "\n".join(["破壊的な手順があります", *lines, "--allow-destructive で適用できます"])
        )
    # 読み込んだ後にファイルが変わっていないかを、読み込んだ内容との比較とハッシュで確認する
    original = target.file.read_text(encoding="utf-8")
    if dump_roundtrip(load_roundtrip(original)) != dump_roundtrip(data):
        raise MigrationFailedError(f"{target.file}: 読み込んだ後に変わったため書き換えません")
    digest = content_hash(original)
    kept: list[str] = []
    for step in steps:
        if step.op == "export_sources" and export_source is not None:
            kept = _export_sources(data, export_source, project_index)
            continue
        apply_step(data, step)
    previous_version = str(data["version"])
    data["version"] = DoubleQuotedScalarString(target.current)
    text = dump_roundtrip(data)
    violations = validate_terminal_config(load_yaml(text))
    # 適用した結果が新しいスキーマに違反するときは書き込まない
    if violations:
        raise MigrationFailedError("\n".join(f"{v.path}: {v.rule}" for v in violations))
    if content_hash(target.file.read_text(encoding="utf-8")) != digest:
        raise MigrationFailedError(f"{target.file}: 読み込んだ後に変わったため書き換えません")
    backup = target.file.with_name(
        BACKUP_FORMAT.format(name=target.file.name, time=now.strftime(BACKUP_TIME_FORMAT))
    )
    replace_file(backup, original)
    replace_file(target.file, text)
    logger.info(
        "設定を移し替えた（%s・%s から %s・バックアップ %s・移さなかった行 %s）",
        target.file,
        previous_version,
        target.current,
        backup,
        kept,
    )
    return MigrationOutcome(backup=backup, kept=kept)
