from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs.features.settings.query import (
    config_path,
    listen_port,
    load_terminal_config,
    state_dir_path,
    validate_terminal_config,
    xdg_base_dir,
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


def test_config_path_when_xdg_config_home_set() -> None:
    """XDG_CONFIG_HOME の下（正常系）。"""
    # 準備
    env = {"XDG_CONFIG_HOME": "/tmp/c"}
    # 実行
    result = config_path(env)
    # 検証
    assert result == Path("/tmp/c/dev-docs/settings.yaml")


def test_xdg_base_dir() -> None:
    """絶対パスの値（正常系）。"""
    # 準備
    env = {"XDG_STATE_HOME": "/tmp/s"}
    # 実行
    result = xdg_base_dir(env, "XDG_STATE_HOME", "~/.local/state")
    # 検証
    assert result == Path("/tmp/s")


@pytest.mark.parametrize("env", [{}, {"XDG_STATE_HOME": ""}, {"XDG_STATE_HOME": "rel"}])
def test_xdg_base_dir_when_unset_or_relative(
    env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """未設定・空の文字列・相対パスは既定（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", "/home/u")
    # 実行
    result = xdg_base_dir(env, "XDG_STATE_HOME", "~/.local/state")
    # 検証
    assert result == Path("/home/u/.local/state")


def test_state_dir_path() -> None:
    """環境変数が端末の設定より優先（正常系）。"""
    # 準備
    env = {"DEV_DOCS_STATE_DIR": "/tmp/b", "XDG_STATE_HOME": "/tmp/c"}
    # 実行
    result = state_dir_path("/tmp/a", env)
    # 検証
    assert result == Path("/tmp/b")


def test_state_dir_path_when_config_value() -> None:
    """端末の設定の値（正常系）。"""
    # 準備
    env = {"XDG_STATE_HOME": "/tmp/c"}
    # 実行
    result = state_dir_path("/tmp/a", env)
    # 検証
    assert result == Path("/tmp/a")


def test_state_dir_path_when_xdg_state_home_set() -> None:
    """XDG_STATE_HOME の下（正常系）。"""
    # 準備
    env = {"XDG_STATE_HOME": "/tmp/c"}
    # 実行
    result = state_dir_path(None, env)
    # 検証
    assert result == Path("/tmp/c/dev-docs")


def test_state_dir_path_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """どれも無い（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", "/home/u")
    # 実行
    result = state_dir_path(None, {})
    # 検証
    assert result == Path("/home/u/.local/state/dev-docs")


def _write(tmp_path: Path, text: str) -> Path:
    """端末の設定をファイルに書き込み、そのパスを返却する。"""
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_terminal_config(tmp_path: Path) -> None:
    """既定値を埋める（正常系）。"""
    # 準備
    path = _write(tmp_path, 'version: "2"\nclone: /tmp/clone\n')
    # 実行
    result = load_terminal_config(path)
    # 検証
    assert result.port == 8781
    assert result.bind == "127.0.0.1"
    assert result.project_index == "http://127.0.0.1:8786"
    assert result.leftover_sources == []
    assert result.log_dir == result.state_dir / "logs"


def test_load_terminal_config_when_state_dir_env_set(tmp_path: Path) -> None:
    """状態の配置先を環境変数で決める（正常系）。"""
    # 準備
    path = _write(tmp_path, 'version: "2"\nclone: /tmp/clone\nstate_dir: /tmp/a\n')
    env = {"DEV_DOCS_STATE_DIR": "/tmp/b"}
    # 実行
    result = load_terminal_config(path, env=env)
    # 検証
    assert result.state_dir == Path("/tmp/b")
    assert result.log_dir == Path("/tmp/b/logs")


def test_load_terminal_config_when_missing(tmp_path: Path) -> None:
    """ファイルが無い（異常系）。"""
    # 準備
    path = tmp_path / "none.yaml"
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        load_terminal_config(path)
    assert str(path) in exc_info.value.message


def test_load_terminal_config_when_yaml_broken(tmp_path: Path) -> None:
    """YAML として読み込めない（異常系）。"""
    # 準備
    path = _write(tmp_path, "sources: [\n")
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        load_terminal_config(path)
    assert len(exc_info.value.violations) == 1
    assert exc_info.value.violations[0].rule.count(":") >= 1


def test_load_terminal_config_when_schema_invalid(tmp_path: Path) -> None:
    """違反を全て集める（異常系）。"""
    # 準備
    path = _write(
        tmp_path, 'version: "2"\nclone: /tmp/clone\nport: abc\nproject_index: 127.0.0.1:8786\n'
    )
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError) as exc_info:
        load_terminal_config(path)
    assert sorted(v.path for v in exc_info.value.violations) == ["port", "project_index"]


def test_load_terminal_config_when_leftover_sources(tmp_path: Path) -> None:
    """前のバージョンから残った sources（正常系）。"""
    # 準備
    path = _write(
        tmp_path,
        'version: "2"\nclone: /tmp/clone\nsources:\n'
        "  - id: sample\n    config: /s/project-index.yaml\n"
        "  - config: /x/project-index.yaml\n",
    )
    # 実行
    result = load_terminal_config(path)
    # 検証
    assert result.leftover_sources == ["sample", "/x/project-index.yaml"]


def _valid_settings() -> dict[str, object]:
    """必須のキーだけを持つ端末の設定の値を返却する。"""
    return {"version": "2", "clone": "/tmp/clone"}


def test_validate_terminal_config() -> None:
    """違反が無い（正常系）。"""
    # 準備
    value = _valid_settings()
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert result == []


def test_validate_terminal_config_when_newer_version() -> None:
    """新しいバージョンの設定（正常系）。"""
    # 準備
    value = _valid_settings()
    value["version"] = "3"
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert [v.path for v in result] == ["version"]


def test_validate_terminal_config_when_project_index_invalid() -> None:
    """project-index の接続先が URL でない（正常系）。"""
    # 準備
    value = _valid_settings()
    value["project_index"] = "127.0.0.1:8786"
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert [v.path for v in result] == ["project_index"]


def test_validate_terminal_config_when_leftover_sources() -> None:
    """残った sources を違反にしない（正常系）。"""
    # 準備
    value = _valid_settings()
    value["sources"] = [{"id": "a"}, {"id": "a", "config": "/b"}]
    # 実行
    result = validate_terminal_config(value)
    # 検証
    assert result == []


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
