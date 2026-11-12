"""端末の設定の読み込み。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from dev_docs.features.settings.types import TerminalConfig, TerminalConfigInvalidError
from dev_docs.shared.errors import Violation
from dev_docs.shared.paths import normalize_path
from dev_docs.shared.schema_check import schema_violations
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

DEFAULT_CONFIG_HOME = "~/.config"
CONFIG_FILE = "dev-docs/settings.yaml"
DEFAULT_STATE_HOME = "~/.local/state"
STATE_SUBDIR = "dev-docs"
XDG_CONFIG_HOME_ENV = "XDG_CONFIG_HOME"
XDG_STATE_HOME_ENV = "XDG_STATE_HOME"
CONFIG_ENV = "DEV_DOCS_CONFIG"
PORT_ENV = "DEV_DOCS_PORT"
STATE_DIR_ENV = "DEV_DOCS_STATE_DIR"
SETTINGS_SCHEMA = "schemas/settings.schema.yaml"
SETTINGS_VERSION = "2"
PORT_MIN = 1
PORT_MAX = 65535


def xdg_base_dir(env: Mapping[str, str], name: str, default: str) -> Path:
    """XDG の環境変数の値を、空の文字列か相対パスなら既定に替えて返す。"""
    value = env.get(name) or ""
    # XDG Base Directory Specification は相対パスを無効として無視する
    return normalize_path(value if os.path.isabs(value) else default)


def config_path(env: Mapping[str, str]) -> Path:
    """環境変数から端末の設定のパスを決める。"""
    value = env.get(CONFIG_ENV)
    if value:
        return normalize_path(value)
    return xdg_base_dir(env, XDG_CONFIG_HOME_ENV, DEFAULT_CONFIG_HOME) / CONFIG_FILE


def state_dir_path(value: str | None, env: Mapping[str, str]) -> Path:
    """環境変数と端末の設定の `state_dir` から状態の置き場を決める。"""
    override = env.get(STATE_DIR_ENV)
    if override:
        return normalize_path(override)
    if value:
        return normalize_path(value)
    return xdg_base_dir(env, XDG_STATE_HOME_ENV, DEFAULT_STATE_HOME) / STATE_SUBDIR


def _settings_schema() -> dict[str, Any]:
    """配布に同梱した端末の設定のスキーマを読む。"""
    text = resources.files("dev_docs").joinpath(SETTINGS_SCHEMA).read_text(encoding="utf-8")
    schema: dict[str, Any] = load_yaml(text)
    return schema


def validate_terminal_config(value: Any) -> list[Violation]:
    """端末の設定の値をスキーマと行の間の決まりで確かめ、違反を全て返す。"""
    violations = schema_violations(_settings_schema(), value)
    if not isinstance(value, dict):
        return violations
    # 前のバージョンから残った sources は検証しない（起動が警告のログに出す）
    # 読めるバージョンより新しい設定
    version = value.get("version")
    if isinstance(version, str) and version.isdigit() and int(version) > int(SETTINGS_VERSION):
        violations.append(Violation(path="version", rule="このサーバーより新しい設定です"))
    return violations


def load_terminal_config(path: Path, *, env: Mapping[str, str] | None = None) -> TerminalConfig:
    """`settings.yaml` を読み、スキーマの違反を全て集めてから端末の設定にする。"""
    if not path.is_file():
        raise TerminalConfigInvalidError(file=path, message=f"{path}: 端末の設定が見つかりません")
    try:
        value = load_yaml(path.read_text(encoding="utf-8"), file=str(path))
    except YamlLoadError as error:
        location = f"{error.line}:{error.column}: " if error.line else ""
        raise TerminalConfigInvalidError(
            file=path,
            message=str(error),
            violations=[Violation(path="$", rule=f"{location}{error.reason}")],
        ) from error
    violations = validate_terminal_config(value if value is not None else {})
    if violations:
        raise TerminalConfigInvalidError(
            file=path,
            message=f"{path}: 端末の設定に違反が {len(violations)} 件あります",
            violations=violations,
        )
    value = value or {}
    state_dir = state_dir_path(value.get("state_dir"), os.environ if env is None else env)
    log_dir = normalize_path(value["log_dir"]) if "log_dir" in value else state_dir / "logs"
    values: dict[str, Any] = {
        key: value[key] for key in ("port", "bind", "project_index") if key in value
    }
    return TerminalConfig(
        file=path,
        version=value["version"],
        clone=normalize_path(value["clone"]),
        state_dir=state_dir,
        log_dir=log_dir,
        leftover_sources=_leftover_ids(value.get("sources")),
        **values,
    )


def _leftover_ids(sources: Any) -> list[str]:
    """前のバージョンから残った `sources` の行の ID（無ければ `config` の先頭）を並べる。"""
    if not isinstance(sources, list):
        return []
    ids: list[str] = []
    for row in sources:
        if not isinstance(row, dict):
            continue
        config = row.get("config")
        first = config[0] if isinstance(config, list) and config else config
        name = row.get("id") or first
        if name:
            ids.append(str(name))
    return ids


def listen_port(config: TerminalConfig, env: Mapping[str, str]) -> int:
    """`DEV_DOCS_PORT` を優先して待ち受けのポートを決める。"""
    raw = env.get(PORT_ENV)
    if not raw:
        return config.port
    if raw.isdecimal() and PORT_MIN <= int(raw) <= PORT_MAX:
        return int(raw)
    raise TerminalConfigInvalidError(
        file=config.file,
        message=f"{PORT_ENV}: 1〜65535 の整数にしてください（{raw}）",
    )
