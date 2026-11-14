"""`dev-docs migrate` の対象の決定・手順の一覧・適用。"""

from __future__ import annotations

import logging
import re
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
    MigrationOutcome,
    MigrationStep,
    MigrationTarget,
    ProjectIndexUnreachableMigrationError,
    SourcesPort,
)
from dev_docs.features.settings.query import (
    SETTINGS_VERSION,
    config_path,
    validate_terminal_config,
)
from dev_docs.integrations.project_index.types import SettingsSourcesView
from dev_docs.shared.errors import (
    InvalidArgumentError,
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
HTTP_CONFLICT = 409
# 保存の違反の `errors[].path` のうち、送信した行の位置を指す先頭
SENT_ROW_PATH = re.compile(r"\Asources\[(\d+)\]")


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
    data: CommentedMap, port: SourcesPort, project_index: str
) -> tuple[list[str], list[str]]:
    """`sources` の行を project-index の端末の設定の今の行に加えて 1 回で保存し、移した行を除く。

    移さなかった行の ID と、ID を求められなかった行の `config` を返却する。
    """
    view = _fetch(port)
    current = _current_rows(view)
    rows = data.get(SOURCES_KEY)
    kept_rows: list[Any] = []
    kept: list[str] = []
    unresolved: list[str] = []
    adding: list[tuple[str, dict[str, Any]]] = []
    for row in rows if isinstance(rows, list) else []:
        plain = _plain_row(row)
        source_id = _source_id(plain)
        # project-index と同じ求め方で ID を求められない行は、照らせないため移さない
        if source_id is None:
            kept_rows.append(row)
            unresolved.append(", ".join(str(item) for item in plain.get("config") or []))
            continue
        if source_id in current:
            # 同じ ID で内容の違う行は、どちらが正しいか決められないため残す
            if current[source_id] != _content(plain):
                kept_rows.append(row)
                kept.append(source_id)
            continue
        adding.append((source_id, plain))
    if adding:
        _save(port, view, adding)
    if kept_rows:
        data[SOURCES_KEY] = kept_rows
    elif SOURCES_KEY in data:
        del data[SOURCES_KEY]
    if PROJECT_INDEX_KEY not in data:
        data[PROJECT_INDEX_KEY] = project_index
    return kept, unresolved


def _fetch(port: SourcesPort) -> SettingsSourcesView:
    """project-index の端末の設定を取得し、取得できないことを移し替えの例外に変える。"""
    try:
        return port.fetch()
    except ProjectIndexUnreachableError as error:
        raise ProjectIndexUnreachableMigrationError(error.address, error.reason) from error
    except (ProjectIndexResponseError, ProjectIndexRejectedError, InvalidArgumentError) as error:
        raise MigrationFailedError(str(error.message)) from error


def _save(
    port: SourcesPort, view: SettingsSourcesView, adding: list[tuple[str, dict[str, Any]]]
) -> None:
    """取得した行に加える行を足し、取得したときの内容のバージョンで照合して 1 回で保存する。"""
    payload = [_sent_row(row) for row in view.rows] + [_sent_row(row) for _, row in adding]
    ids = [_view_id(view, index) for index in range(len(view.rows))] + [
        source_id for source_id, _ in adding
    ]
    try:
        port.save(payload, view.version)
    except ProjectIndexUnreachableError as error:
        # 保存した後の読み直しを待てなかっただけのことがあるため、取得し直して確かめる
        try:
            again = port.fetch()
        except ProjectIndexUnreachableError as retry:
            raise ProjectIndexUnreachableMigrationError(retry.address, retry.reason) from retry
        except (ProjectIndexResponseError, InvalidArgumentError) as retry:
            raise MigrationFailedError(str(retry.message)) from retry
        saved = _current_rows(again)
        if all(saved.get(source_id) == _content(row) for source_id, row in adding):
            return
        raise ProjectIndexUnreachableMigrationError(
            error.address, error.reason, unconfirmed=True
        ) from error
    except (InvalidArgumentError, ProjectIndexRejectedError) as error:
        lines = [f"project-index が {error.status} を返しました: {error.message}"]
        for violation in error.violations:
            match = SENT_ROW_PATH.match(violation.path)
            if match and int(match[1]) < len(ids):
                lines.append(f"{ids[int(match[1])]}: {violation.rule}")
            else:
                lines.append(f"{violation.path}: {violation.rule}")
        raise MigrationFailedError("\n".join(lines)) from error
    except ProjectIndexResponseError as error:
        message = str(error.message)
        if error.status_code == HTTP_CONFLICT:
            message += (
                "\n取得した後に project-index の端末の設定が変わりました。"
                "dev-docs migrate をやり直してください。"
            )
        raise MigrationFailedError(message) from error


def _current_rows(view: SettingsSourcesView) -> dict[str, dict[str, Any]]:
    """取得した行を、配信元の ID ごとの比べる内容にする（ID を求められない行は除く）。"""
    current: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(view.rows):
        source_id = _view_id(view, index)
        if source_id is not None:
            current.setdefault(source_id, _content(row))
    return current


def _view_id(view: SettingsSourcesView, index: int) -> str | None:
    """取得した行の配信元の ID（状態の `id`・行の `id`・`config` の `name` の順）を返却する。"""
    state = view.states[index] if index < len(view.states) else None
    if state is not None and state.id:
        return str(state.id)
    return _source_id(view.rows[index])


def _source_id(row: Mapping[str, Any]) -> str | None:
    """行の配信元の ID を、`id`、無ければ `config` の配信元の設定を重ねた `name` で求める。"""
    if row.get("id"):
        return str(row["id"])
    merged: dict[str, Any] = {}
    for item in row.get("config") or []:
        # 読めない設定のファイルは飛ばし、読めたファイルだけを重ねる（project-index と同じ）
        try:
            value = load_yaml(Path(str(item)).expanduser().read_text(encoding="utf-8"))
        except OSError, YamlLoadError:
            continue
        if isinstance(value, Mapping):
            merged.update(value)
    name = merged.get("name")
    return name if isinstance(name, str) and name else None


def _content(row: Mapping[str, Any]) -> dict[str, Any]:
    """行の内容を、既定値と同じキーを除いた `config`・`enabled`・`scope`・`outside_read` にする。"""
    content: dict[str, Any] = {"config": [str(item) for item in row.get("config") or []]}
    if row.get("enabled", True) is not True:
        content["enabled"] = row.get("enabled")
    if row.get("outside_read", True) is not True:
        content["outside_read"] = row.get("outside_read")
    scope = row.get("scope") or {}
    if isinstance(scope, Mapping):
        if scope.get("read"):
            content["read"] = list(scope["read"])
        if scope.get("write") is not None:
            content["write"] = list(scope["write"])
    else:
        content["scope"] = scope
    return content


def _sent_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """行を、保存で送信する `id`・`config`・`enabled`・`scope`・`outsideRead` のキーだけにする。"""
    sent: dict[str, Any] = {}
    if row.get("id"):
        sent["id"] = row["id"]
    sent["config"] = list(row.get("config") or [])
    for key in ("enabled", "scope"):
        if key in row:
            sent[key] = row[key]
    if "outside_read" in row:
        sent["outsideRead"] = row["outside_read"]
    return sent


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
    sources_port: SourcesPort | None,
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
    unresolved: list[str] = []
    for step in steps:
        if step.op == "export_sources" and sources_port is not None:
            kept, unresolved = _export_sources(data, sources_port, project_index)
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
        "設定を移し替えた（%s・%s から %s・バックアップ %s・移さなかった行 %s・ID を求められなかった行 %s）",
        target.file,
        previous_version,
        target.current,
        backup,
        kept,
        unresolved,
    )
    return MigrationOutcome(backup=backup, kept=kept, unresolved=unresolved)
