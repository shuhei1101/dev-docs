from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs.features.settings.query import (
    config_path,
    listen_port,
    load_terminal_config,
    validate_terminal_config,
)
from dev_docs.features.settings.types import TerminalConfig, TerminalConfigInvalidError


def test_config_path() -> None:
    """環境変数の値（正常系）。"""
    # 準備
    env = {"DEV_DOCS_CONFIG": "/tmp/x/settings.yaml"}
    # 実行
    result = config_path(env)
    # 検証
    assert result == Path("/tmp/x/settings.yaml")


def test_config_path_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数が無い（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", "/home/u")
    env = {"HOME": "/home/u"}
    # 実行
    result = config_path(env)
    # 検証
    assert result == Path("/home/u/.config/dev-docs/settings.yaml")


def test_load_terminal_config(tmp_path: Path) -> None:
    """既定値を埋める（正常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(
        'version: "1"\nclone: /tmp/clone\nsources:\n  - config: /tmp/a/dev-docs.yaml\n',
        encoding="utf-8",
    )
    # 実行
    result = load_terminal_config(path)
    # 検証
    assert result.port == 8781
    assert result.bind == "127.0.0.1"
    assert result.sources[0].config == ["/tmp/a/dev-docs.yaml"]
    assert result.log_dir == result.state_dir / "logs"


def test_load_terminal_config_when_missing(tmp_path: Path) -> None:
    """ファイルが無い（異常系）。"""
    # 準備
    path = tmp_path / "none.yaml"
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        load_terminal_config(path)
    assert str(path) in exc_info.value.message


def test_load_terminal_config_when_yaml_broken(tmp_path: Path) -> None:
    """YAML として読めない（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text("sources: [\n", encoding="utf-8")
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        load_terminal_config(path)
    assert len(exc_info.value.violations) == 1
    assert exc_info.value.violations[0].rule.count(":") >= 1


def test_load_terminal_config_when_schema_invalid(tmp_path: Path) -> None:
    """違反を全て集める（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(
        'version: "1"\nclone: /tmp/clone\nport: abc\nsources:\n  - id: a\n',
        encoding="utf-8",
    )
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        load_terminal_config(path)
    assert sorted(v.path for v in exc_info.value.violations) == ["port", "sources[0].config"]


def _valid_settings() -> dict[str, object]:
    """必須のキーだけを持つ端末の設定の値を返す。"""
    return {"version": "1", "clone": "/tmp/clone", "sources": [{"config": "/tmp/a/dev-docs.yaml"}]}


def test_validate_terminal_config() -> None:
    """違反が無い（正常系）。"""
    # 準備
    value = _valid_settings()
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert result == []


def test_validate_terminal_config_when_duplicate_id() -> None:
    """行の ID が重なる（正常系）。"""
    # 準備
    value = _valid_settings()
    value["sources"] = [
        {"id": "a", "config": "/tmp/a/dev-docs.yaml"},
        {"id": "a", "config": "/tmp/b/dev-docs.yaml"},
    ]
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert [v.path for v in result] == ["sources[1].id"]


def test_validate_terminal_config_when_empty_glob() -> None:
    """空の glob（正常系）。"""
    # 準備
    value = _valid_settings()
    value["sources"] = [{"config": "/tmp/a/dev-docs.yaml", "scope": {"read": [""]}}]
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert [v.path for v in result] == ["sources[0].scope.read[0]"]


def test_validate_terminal_config_when_newer_version() -> None:
    """新しいバージョンの設定（正常系）。"""
    # 準備
    value = _valid_settings()
    value["version"] = "2"
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert [v.path for v in result] == ["version"]


def test_listen_port(make_terminal_config: Callable[..., TerminalConfig]) -> None:
    """環境変数が優先（正常系）。"""
    # 準備
    config = make_terminal_config(port=9000)
    # 実行
    result = listen_port(config, {"DEV_DOCS_PORT": "9100"})
    # 検証
    assert result == 9100


def test_listen_port_when_unset(make_terminal_config: Callable[..., TerminalConfig]) -> None:
    """設定の値（正常系）。"""
    # 準備
    config = make_terminal_config(port=9000)
    # 実行
    result = listen_port(config, {})
    # 検証
    assert result == 9000


def test_listen_port_when_invalid(make_terminal_config: Callable[..., TerminalConfig]) -> None:
    """整数でない（異常系）。"""
    # 準備
    config = make_terminal_config(port=9000)
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        listen_port(config, {"DEV_DOCS_PORT": "abc"})
    assert "DEV_DOCS_PORT" in exc_info.value.message
