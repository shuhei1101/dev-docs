"""端末の設定の読み込み。"""

from __future__ import annotations

from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from dev_docs.features.settings.types import SourceEntry, TerminalConfig, TerminalConfigInvalidError
from dev_docs.shared.errors import Violation
from dev_docs.shared.paths import normalize_path
from dev_docs.shared.schema_check import schema_violations
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

DEFAULT_CONFIG_PATH = "~/.config/dev-docs/settings.yaml"
CONFIG_ENV = "DEV_DOCS_CONFIG"
PORT_ENV = "DEV_DOCS_PORT"
SETTINGS_SCHEMA = "schemas/settings.schema.yaml"
SETTINGS_VERSION = "1"
DEFAULT_STATE_DIR = "~/.local/state/dev-docs"
PORT_MIN = 1
PORT_MAX = 65535


def config_path(env: Mapping[str, str]) -> Path:
    """環境変数から端末の設定のパスを決める。"""
    return normalize_path(env.get(CONFIG_ENV) or DEFAULT_CONFIG_PATH)


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
    sources = value.get("sources")
    if isinstance(sources, list):
        seen: set[str] = set()
        for index, row in enumerate(sources):
            if not isinstance(row, dict):
                continue
            # 行の ID が先の行と重なる（id を省いた行は配信元の読み込みで比べる）
            row_id = row.get("id")
            if isinstance(row_id, str):
                if row_id in seen:
                    violations.append(
                        Violation(
                            path=f"sources[{index}].id",
                            rule=f"{row_id} は既に使われています",
                            fix="別の ID にしてください",
                        )
                    )
                seen.add(row_id)
            # 作業場所の glob に空の文字列がある
            scope = row.get("scope")
            if isinstance(scope, dict):
                for key in ("read", "write"):
                    globs = scope.get(key)
                    if not isinstance(globs, list):
                        continue
                    for position, glob in enumerate(globs):
                        if glob == "":
                            violations.append(
                                Violation(
                                    path=f"sources[{index}].scope.{key}[{position}]",
                                    rule="空の文字列は書けません",
                                )
                            )
    # 読めるバージョンより新しい設定
    version = value.get("version")
    if isinstance(version, str) and version.isdigit() and int(version) > int(SETTINGS_VERSION):
        violations.append(Violation(path="version", rule="このサーバーより新しい設定です"))
    return violations


def load_terminal_config(path: Path) -> TerminalConfig:
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
    state_dir = normalize_path(value.get("state_dir", DEFAULT_STATE_DIR))
    log_dir = normalize_path(value["log_dir"]) if "log_dir" in value else state_dir / "logs"
    values: dict[str, Any] = {
        key: value[key]
        for key in ("port", "bind", "seen_retention_days", "script_timeout_sec")
        if key in value
    }
    return TerminalConfig(
        file=path,
        version=value["version"],
        clone=normalize_path(value["clone"]),
        state_dir=state_dir,
        log_dir=log_dir,
        sources=[SourceEntry.model_validate(row) for row in value.get("sources", [])],
        **values,
    )


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
