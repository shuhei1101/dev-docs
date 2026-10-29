from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

NEW_VERSION = "0.3.0"
RENAME_STEPS = (
    "steps:\n"
    "  - op: rename\n"
    "    path: script_timeout_sec\n"
    "    to: script_timeout_seconds\n"
    "    description: script_timeout_sec を script_timeout_seconds に改名する\n"
)
# 1 つ目は改名でき、2 つ目は改名先のキーが 1 つ目で出来ているため失敗する
FAILING_STEPS = (
    "steps:\n"
    "  - op: rename\n"
    "    path: script_timeout_sec\n"
    "    to: script_timeout_seconds\n"
    "    description: 1 つ目の手順\n"
    "  - op: rename\n"
    "    path: seen_retention_days\n"
    "    to: script_timeout_seconds\n"
    "    description: 2 つ目の手順\n"
)
OLD_SETTINGS_EXTRA = "script_timeout_sec: 20"


def _served_ids(status: dict[str, Any]) -> set[str]:
    """`status` が配信中として返した配信元の ID を集める。"""
    return {source["id"] for source in status["sources"] if source["status"] == "serving"}


def test_normal(
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve_from_clone: Callable[..., Any],
    wait_for_new_version: Callable[..., Any],
    serve_pid_count: Callable[[int], int],
) -> None:
    """管理の MCP の `update` でクローンを新しいバージョンにして起動し直す（正常系）。"""
    # 準備
    clone = make_clone()
    served = serve_from_clone(clone, make_source("sample"), make_source("notes", git=False))
    previous = served.call_admin("status", format="json").data["version"]
    upstream = clone.push_upstream(clone.bump_version(NEW_VERSION), "bump")
    # 実行
    updated = served.update()
    status = wait_for_new_version(served.port, NEW_VERSION)
    # 検証
    assert not updated.is_error
    assert updated.data["previous_version"] == previous
    assert updated.data["version"] == NEW_VERSION
    assert updated.data["updated"] is True
    assert updated.data["migration_needed"] is False
    assert updated.data["restarting"] is True
    assert status["version"] == NEW_VERSION
    assert _served_ids(status) == {"sample", "notes"}
    assert serve_pid_count(served.port) == 1
    assert clone.head() == upstream


def test_normal_when_terminal_config_old(
    tmp_path: Path,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve_from_clone: Callable[..., Any],
    wait_for_new_version: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """端末の設定が古くなるときは再起動せず、移し替えを当ててから再起動する（正常系）。"""
    # 準備
    clone = make_clone()
    served = serve_from_clone(
        clone,
        make_source("sample"),
        make_source("notes", git=False),
        extra=OLD_SETTINGS_EXTRA,
    )
    settings = served.settings
    original = settings.read_text(encoding="utf-8")
    previous = served.call_admin("status", format="json").data["version"]
    files = {**clone.bump_version(NEW_VERSION), **clone.next_settings_version(RENAME_STEPS)}
    clone.push_upstream(files, "migration")
    # 実行
    updated = served.update()
    still_running = served.call_admin("status", format="json").data
    plan = clone.migrate(settings, "--plan")
    after_plan = settings.read_text(encoding="utf-8")
    migrated = clone.migrate(settings)
    saved = load_yaml_file(settings)
    restarted = served.call_admin("restart")
    status = wait_for_new_version(served.port, NEW_VERSION)
    # 検証
    backups = sorted(settings.parent.glob("settings.yaml.bak-*"))
    assert updated.data["updated"] is True
    assert updated.data["migration_needed"] is True
    assert updated.data["restarting"] is False
    assert still_running["version"] == previous
    assert plan.returncode == 0
    assert "script_timeout_sec を script_timeout_seconds に改名する" in plan.stdout
    assert after_plan == original
    assert migrated.returncode == 0
    assert saved["version"] == "2"
    assert saved["script_timeout_seconds"] == 20
    assert "script_timeout_sec" not in saved
    assert [backup.read_text(encoding="utf-8") for backup in backups] == [original]
    assert not restarted.is_error
    assert status["version"] == NEW_VERSION
    assert _served_ids(status) == {"sample", "notes"}


def test_error_when_migration_fails(tmp_path: Path, make_clone: Callable[..., Any]) -> None:
    """移し替えの手順が失敗すると、端末の設定を元のままにして失敗した手順と理由を出す（異常系）。"""
    # 準備
    clone = make_clone()
    clone.write_local(clone.next_settings_version(FAILING_STEPS, root=clone.clone))
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        'version: "1"\n'
        f"clone: {clone.clone}\n"
        "script_timeout_sec: 20\n"
        "seen_retention_days: 7\n"
        "sources: []\n",
        encoding="utf-8",
    )
    original = settings.read_bytes()
    # 実行
    migrated = clone.migrate(settings)
    # 検証
    assert migrated.returncode != 0
    assert settings.read_bytes() == original
    assert "seen_retention_days" in migrated.stderr
    assert "改名できません" in migrated.stderr


def test_error_when_pull_fails(
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve_from_clone: Callable[..., Any],
    serve_pid_count: Callable[[int], int],
) -> None:
    """クローンを更新できないと git のエラーを返し、再起動せず前のバージョンで配信を続ける（異常系）。"""
    # 準備
    clone = make_clone()
    served = serve_from_clone(clone, make_source("sample"))
    previous = served.call_admin("status", format="json").data
    head = clone.head()
    local = (clone.clone / "pyproject.toml").read_text(encoding="utf-8") + "# 手元の変更\n"
    clone.write_local({"pyproject.toml": local})
    clone.push_upstream(clone.bump_version(NEW_VERSION), "upstream")
    # 実行
    updated = served.update()
    status = served.call_admin("status", format="json").data
    # 検証
    assert updated.is_error
    assert "git pull" in updated.text
    assert status["version"] == previous["version"]
    assert status["pid"] == previous["pid"]
    assert _served_ids(status) == {"sample"}
    assert serve_pid_count(served.port) == 1
    assert clone.head() == head
    assert (clone.clone / "pyproject.toml").read_text(encoding="utf-8") == local
