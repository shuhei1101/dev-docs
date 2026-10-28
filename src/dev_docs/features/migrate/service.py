"""`dev-docs migrate` の対象の決定・手順の一覧・適用。"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
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
    MigrationStep,
    MigrationTarget,
)
from dev_docs.features.settings.query import (
    SETTINGS_VERSION,
    config_path,
    validate_terminal_config,
)
from dev_docs.features.sources.service import validate_source_config
from dev_docs.features.sources.types import SOURCE_CONFIG_VERSION
from dev_docs.shared.errors import Violation
from dev_docs.shared.files import replace_file
from dev_docs.shared.hashing import content_hash
from dev_docs.shared.paths import normalize_path
from dev_docs.shared.yaml_io import YamlLoadError, dump_roundtrip, load_roundtrip, load_yaml

logger = logging.getLogger(__name__)


def resolve_target(source: str | None, *, env: Mapping[str, str]) -> MigrationTarget:
    """`--source` の有無で移し替える設定を決める。"""
    if source is not None:
        return MigrationTarget(
            kind="dev-docs", file=normalize_path(source), current=SOURCE_CONFIG_VERSION
        )
    return MigrationTarget(kind="settings", file=config_path(env), current=SETTINGS_VERSION)


def plan_migration(target: MigrationTarget) -> tuple[CommentedMap, list[MigrationStep]]:
    """対象の `version` を読み、当てる手順を求める。"""
    try:
        data = load_roundtrip(target.file.read_text(encoding="utf-8"), file=str(target.file))
    except (OSError, YamlLoadError) as error:
        raise MigrationConfigInvalidError(f"{target.file}: {error}") from error
    version = str(data["version"]) if "version" in data else ""
    if not version.isdecimal():
        raise MigrationConfigInvalidError(
            f"{target.file}: version が整数の文字列で書かれていません"
        )
    state = version_state(version, target.current)
    # 新しすぎる設定は移し替えない
    if state == "newer":
        raise ConfigNewerError(
            f"{target.file}: 設定のバージョン {version} が dev-docs の読める {target.current}"
            " より新しい。dev-docs を更新してください"
        )
    if state == "current":
        return data, []
    return data, load_steps(target.kind, mine=version, current=target.current)


def _violations(target: MigrationTarget, value: dict[str, Any]) -> list[Violation]:
    """当てた結果を、対象の種類の新しいスキーマで確かめる。"""
    if target.kind == "settings":
        return validate_terminal_config(value)
    return validate_source_config(value, root=target.file.parent)


def apply_migration(
    target: MigrationTarget,
    data: CommentedMap,
    steps: list[MigrationStep],
    *,
    allow_destructive: bool,
    now: datetime,
) -> Path:
    """手順を全て当てて新しいスキーマで検証し、バックアップを取ってから 1 回だけ書き込む。"""
    # 破壊的な手順は、許されたときだけ当てる
    destructive = [step for step in steps if step.destructive]
    if destructive and not allow_destructive:
        lines = [f"{step.version}: {step.description}" for step in destructive]
        raise DestructiveStepBlockedError(
            "\n".join(["破壊的な手順があります", *lines, "--allow-destructive で当てられます"])
        )
    # 読んだ後にファイルが変わっていないかを、読んだ内容との比較とハッシュで確かめる
    original = target.file.read_text(encoding="utf-8")
    if dump_roundtrip(load_roundtrip(original)) != dump_roundtrip(data):
        raise MigrationFailedError(f"{target.file}: 読んだ後に変わったため書き換えません")
    digest = content_hash(original)
    for step in steps:
        apply_step(data, step)
    previous_version = str(data["version"])
    data["version"] = DoubleQuotedScalarString(target.current)
    text = dump_roundtrip(data)
    violations = _violations(target, load_yaml(text))
    # 当てた結果が新しいスキーマに違反するときは書かない
    if violations:
        raise MigrationFailedError("\n".join(f"{v.path}: {v.rule}" for v in violations))
    if content_hash(target.file.read_text(encoding="utf-8")) != digest:
        raise MigrationFailedError(f"{target.file}: 読んだ後に変わったため書き換えません")
    backup = target.file.with_name(
        BACKUP_FORMAT.format(name=target.file.name, time=now.strftime(BACKUP_TIME_FORMAT))
    )
    replace_file(backup, original)
    replace_file(target.file, text)
    logger.info(
        "設定を移し替えた（%s・%s から %s・バックアップ %s）",
        target.file,
        previous_version,
        target.current,
        backup,
    )
    return backup
