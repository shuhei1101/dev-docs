from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.features.settings.query import SETTINGS_VERSION

SETTINGS_SCHEMA = (
    Path(__file__).parents[3] / "src" / "dev_docs" / "schemas" / "settings.schema.yaml"
)
TOOL_COUNT = 6
RENAME_STEPS = (
    "steps:\n"
    "  - op: rename\n"
    "    path: script_timeout_sec\n"
    "    to: script_timeout_seconds\n"
    "    description: script_timeout_sec を script_timeout_seconds に改名する\n"
)
SETUP_PROMPT = "/dev-docs:global-setup {clone}"
LOCATION_PATTERN = r"場所|パス|settings\.yaml"


def _terminal_settings(
    path: Path, clone: Path | None, *, version: str, extra: str = "", sources: str = "[]"
) -> None:
    """端末の設定の YAML を書く（`clone` が `None` なら `clone` のキーを持たない）。"""
    lines = [f'version: "{version}"']
    if clone is not None:
        lines.append(f"clone: {clone}")
    lines.append(f"state_dir: {path.parent / 'state'}")
    if extra:
        lines.append(extra.rstrip("\n"))
    lines.append(f"sources: {sources}" if sources == "[]" else f"sources:\n{sources}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_normal(
    tmp_path: Path,
    claude_home: Any,
    make_clone: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
    schema_errors: Callable[[Path, Any], list[str]],
    list_mcp_tools: Callable[[int], list[str]],
    serve_pid_count: Callable[[int], int],
) -> None:
    """端末の設定・Claude Code の env・起動を用意し、`/mcp` につながることを確かめる（正常系）。"""
    # 準備
    clone = make_clone(sync=False)
    settings = tmp_path / "terminal" / "settings.yaml"
    settings.parent.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    # 実行
    run = claude_home.run(
        SETUP_PROMPT.format(clone=clone.clone),
        cwd=work,
        answers=[(LOCATION_PATTERN, str(settings))],
    )
    # 検証
    saved = load_yaml_file(settings)
    env = claude_home.settings_json()["env"]
    assert not run.result["is_error"]
    assert saved["version"] == SETTINGS_VERSION
    assert saved["clone"] == str(clone.clone)
    assert saved["sources"] == []
    assert schema_errors(SETTINGS_SCHEMA, saved) == []
    assert env["DEV_DOCS_CONFIG"] == str(settings)
    assert env["E2E_KEEP"] == "keep"
    assert serve_pid_count(claude_home.port) == 1
    assert len(list_mcp_tools(claude_home.port)) == TOOL_COUNT
    assert str(settings) in run.text
    assert "/dev-docs:setup" in run.text
    assert claude_home.real_changes() == []


def test_normal_when_terminal_config_lacks_keys(
    tmp_path: Path,
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """端末の設定に足りないキーだけを聞いて書き足す（正常系）。"""
    # 準備
    clone = make_clone()
    sample = make_source("sample")
    settings = tmp_path / "terminal" / "settings.yaml"
    settings.parent.mkdir()
    rows = (
        "  - id: sample\n"
        "    config:\n"
        f"      - {sample.folder / 'dev-docs.yaml'}\n"
        "    scope:\n"
        "      read:\n"
        f"        - {sample.folder}\n"
    )
    _terminal_settings(settings, None, version=SETTINGS_VERSION, sources=rows)
    claude_home.set_env(DEV_DOCS_CONFIG=str(settings))
    before = load_yaml_file(settings)
    # 実行
    run = claude_home.run(
        SETUP_PROMPT.format(clone=clone.clone),
        cwd=tmp_path,
        answers=[(r"clone|クローン", str(clone.clone))],
    )
    # 検証
    saved = load_yaml_file(settings)
    assert not run.result["is_error"]
    assert len(run.questions) == 1
    assert saved["clone"] == str(clone.clone)
    assert saved["sources"] == before["sources"]
    assert {key: value for key, value in saved.items() if key != "clone"} == before
    assert claude_home.settings_json()["env"]["DEV_DOCS_CONFIG"] == str(settings)


def test_normal_when_terminal_config_old(
    tmp_path: Path,
    claude_home: Any,
    make_clone: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """端末の設定が古いと、当てる手順を示して移し替え、バックアップを残す（正常系）。"""
    # 準備
    clone = make_clone()
    clone.write_local(clone.next_settings_version(RENAME_STEPS, root=clone.clone))
    settings = tmp_path / "terminal" / "settings.yaml"
    settings.parent.mkdir()
    _terminal_settings(
        settings, clone.clone, version=SETTINGS_VERSION, extra="script_timeout_sec: 20"
    )
    claude_home.set_env(DEV_DOCS_CONFIG=str(settings))
    original = settings.read_text(encoding="utf-8")
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(clone=clone.clone), cwd=tmp_path)
    # 検証
    saved = load_yaml_file(settings)
    backups = sorted(settings.parent.glob("settings.yaml.bak-*"))
    assert not run.result["is_error"]
    assert saved["version"] == "2"
    assert saved["script_timeout_seconds"] == 20
    assert "script_timeout_sec" not in saved
    assert [backup.read_text(encoding="utf-8") for backup in backups] == [original]
    assert "script_timeout_sec を script_timeout_seconds に改名する" in run.text


def test_error_when_terminal_config_newer(
    tmp_path: Path,
    claude_home: Any,
    make_clone: Callable[..., Any],
) -> None:
    """端末の設定が dev-docs より新しいと、更新を案内して端末の設定も env も書き換えない（異常系）。"""
    # 準備
    clone = make_clone()
    settings = tmp_path / "terminal" / "settings.yaml"
    settings.parent.mkdir()
    newer = str(int(SETTINGS_VERSION) + 1)
    _terminal_settings(settings, clone.clone, version=newer)
    claude_home.set_env(DEV_DOCS_CONFIG=str(settings))
    settings_before = settings.read_bytes()
    claude_before = json.dumps(claude_home.settings_json(), sort_keys=True)
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(clone=clone.clone), cwd=tmp_path)
    # 検証
    assert settings.read_bytes() == settings_before
    assert json.dumps(claude_home.settings_json(), sort_keys=True) == claude_before
    assert newer in run.text
    assert SETTINGS_VERSION in run.text
    assert "update" in run.text
