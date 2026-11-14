from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs import main as main_module
from dev_docs.__main__ import main
from dev_docs.shared.yaml_io import load_yaml

from .conftest import MockIndex

SETTINGS_V1 = 'version: "1"\nclone: /x\nlog_dir: /logs\n'
SOURCES_V1 = (
    'version: "1"\nclone: /x\nsources:\n'
    "  - id: sample\n    config: /repo/sample/dev-docs.yaml\n"
    "  - id: notes\n    config: /repo/notes/dev-docs.yaml\n"
    "  - id: extra\n    config: /repo/extra/dev-docs.yaml\n"
)
EXPORT_SOURCES = {"op": "export_sources", "path": "sources", "description": "project-index へ移す"}
RENAME_LOG_DIR = {"op": "rename", "path": "log_dir", "to": "state_dir", "description": "改名"}


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`version: "1"` の端末の設定を書き込み、`DEV_DOCS_CONFIG` で指す。"""
    path = tmp_path / "settings.yaml"
    path.write_text(SETTINGS_V1, encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(path))
    return path


def _backups(folder: Path) -> list[Path]:
    """フォルダのバックアップのファイルを集める。"""
    return sorted(folder.glob("*.bak-*"))


def test_normal(
    settings_file: Path,
    write_steps: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """古い端末の設定に手順を当て、バックアップを残して version を上げる（正常系）。"""
    # 準備
    write_steps("settings", "2", [RENAME_LOG_DIR])
    # 実行
    plan_code = main(["migrate", "--plan"])
    plan_out = capsys.readouterr().out
    unchanged = settings_file.read_text(encoding="utf-8")
    code = main(["migrate"])
    capsys.readouterr()
    after = settings_file.read_text(encoding="utf-8")
    again_code = main(["migrate"])
    again_out = capsys.readouterr().out
    # 検証
    backups = _backups(settings_file.parent)
    assert plan_code == 0
    assert plan_out.splitlines() == ["2: 改名"]
    assert unchanged == SETTINGS_V1
    assert code == 0
    assert load_yaml(after) == {"version": "2", "clone": "/x", "state_dir": "/logs"}
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == SETTINGS_V1
    assert again_code == 0
    assert "移し替えは要りません" in again_out
    assert settings_file.read_text(encoding="utf-8") == after


def test_normal_when_record_only(settings_file: Path, write_steps: Callable[..., None]) -> None:
    """`--record` で手順を当てずに version だけを書き換える（正常系）。"""
    # 準備
    write_steps("settings", "2", [RENAME_LOG_DIR])
    # 実行
    code = main(["migrate", "--record"])
    # 検証
    assert code == 0
    assert load_yaml(settings_file.read_text(encoding="utf-8")) == {
        "version": "2",
        "clone": "/x",
        "log_dir": "/logs",
    }


def test_error_when_config_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """version の無い設定は移し替えずに終了コード 2 で止める（異常系）。"""
    # 準備
    settings = tmp_path / "settings.yaml"
    text = "clone: /x\n"
    settings.write_text(text, encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(settings))
    # 実行
    code = main(["migrate"])
    # 検証
    assert code == 2
    assert "version" in capsys.readouterr().err
    assert settings.read_text(encoding="utf-8") == text
    assert _backups(tmp_path) == []


def test_error_when_step_fails(
    settings_file: Path,
    write_steps: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """適用した結果が新しいスキーマに違反すると、書き換えず終了コード 4 で止める（異常系）。"""
    # 準備
    write_steps(
        "settings",
        "2",
        [{"op": "rename", "path": "clone", "to": "clone_old", "description": "必須のキーを改名"}],
    )
    # 実行
    code = main(["migrate"])
    # 検証
    error = capsys.readouterr().err
    assert code == 4
    assert "clone" in error
    assert settings_file.read_text(encoding="utf-8") == SETTINGS_V1


def test_error_when_destructive_step_blocked(
    settings_file: Path,
    write_steps: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """破壊的な手順は `--allow-destructive` なしでは触らず終了コード 5 で止める（異常系）。"""
    # 準備
    write_steps("settings", "2", [{"op": "delete", "path": "log_dir", "description": "削除"}])
    # 実行
    blocked = main(["migrate"])
    error = capsys.readouterr().err
    unchanged = settings_file.read_text(encoding="utf-8")
    backups = _backups(settings_file.parent)
    allowed = main(["migrate", "--allow-destructive"])
    # 検証
    assert blocked == 5
    assert "削除" in error
    assert unchanged == SETTINGS_V1
    assert backups == []
    assert allowed == 0
    assert load_yaml(settings_file.read_text(encoding="utf-8")) == {"version": "2", "clone": "/x"}


def test_error_when_config_newer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """dev-docs より新しい version の設定は移し替えず終了コード 6 で止める（異常系）。"""
    # 準備
    settings = tmp_path / "settings.yaml"
    text = 'version: "99"\nclone: /x\n'
    settings.write_text(text, encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(settings))
    # 実行
    code = main(["migrate"])
    # 検証
    assert code == 6
    assert "dev-docs を更新してください" in capsys.readouterr().err
    assert settings.read_text(encoding="utf-8") == text


def _write_v1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    """`sources` を持つ前のバージョンの端末の設定を書き込み、`DEV_DOCS_CONFIG` で指す。"""
    path = tmp_path / name
    path.write_text(SOURCES_V1, encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(path))
    return path


def _requests(mock_index: MockIndex, method: str) -> list[object]:
    """偽物が受けた端末の設定の API の要求の本文を、メソッドで絞って返却する。"""
    return [
        body
        for received, path, body in mock_index.received
        if received == method and path.startswith("/settings/sources")
    ]


def test_normal_when_sources_moved_to_project_index(
    tmp_path: Path,
    mock_index: MockIndex,
    write_steps: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """sources の行を project-index の今の行に加えて 1 回で保存し、dev-docs から除いて project_index を追加する（正常系）。"""
    # 準備
    write_steps("settings", "2", [EXPORT_SOURCES])
    mock_index.rows.append({"id": "extra", "config": ["/repo/other/project-index.yaml"]})
    settings = _write_v1(tmp_path, monkeypatch, "settings.yaml")
    # 実行
    code = main(["migrate", "--project-index", mock_index.address])
    out = capsys.readouterr().out
    fetched = _requests(mock_index, "GET")
    saved = _requests(mock_index, "PUT")
    mock_index.received.clear()
    mock_index.rows = []
    monkeypatch.setenv("PROJECT_INDEX_PORT", str(mock_index.port))
    _write_v1(tmp_path, monkeypatch, "default.yaml")
    default_code = main(["migrate"])
    # 検証
    written = load_yaml(settings.read_text(encoding="utf-8"))
    assert code == 0
    assert len(fetched) == 1
    assert len(saved) == 1
    body = saved[0]
    assert isinstance(body, dict)
    assert [row.get("id") for row in body["sources"]] == ["extra", "sample", "notes"]
    assert body["sources"][0]["config"] == ["/repo/other/project-index.yaml"]
    assert body["expectedVersion"] == "1"
    assert written["sources"] == [{"id": "extra", "config": "/repo/extra/dev-docs.yaml"}]
    assert (written["project_index"], written["version"]) == (mock_index.address, "2")
    assert "extra" in out
    assert "移しませんでした" in out
    assert default_code == 0
    assert len(_requests(mock_index, "PUT")) == 1


def test_normal_when_save_response_exceeds_timeout(
    tmp_path: Path,
    mock_index: MockIndex,
    write_steps: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """保存の応答が制限時間を超えても、再取得して保存を確認し、移し替えを終える（正常系）。"""
    # 準備
    write_steps("settings", "2", [EXPORT_SOURCES])
    mock_index.rows.append({"id": "extra", "config": ["/repo/other/project-index.yaml"]})
    mock_index.put_delay_sec = 3
    monkeypatch.setattr(main_module, "PROJECT_INDEX_TIMEOUT_SEC", 1)
    settings = _write_v1(tmp_path, monkeypatch, "settings.yaml")
    # 実行
    code = main(["migrate", "--project-index", mock_index.address])
    # 検証
    written = load_yaml(settings.read_text(encoding="utf-8"))
    assert code == 0
    assert written["sources"] == [{"id": "extra", "config": "/repo/extra/dev-docs.yaml"}]
    assert (written["project_index"], written["version"]) == (mock_index.address, "2")
    assert len(_requests(mock_index, "GET")) == 2
    assert len(_requests(mock_index, "PUT")) == 1


def test_error_when_project_index_rejects_save(
    tmp_path: Path,
    mock_index: MockIndex,
    write_steps: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """project-index が sources の保存を断ると、どちらの端末の設定も書き換えずに終了コード 4 で止める（異常系）。"""
    # 準備
    write_steps("settings", "2", [EXPORT_SOURCES])
    mock_index.rows.append({"id": "extra", "config": ["/repo/other/project-index.yaml"]})
    # 送信する行は extra・sample・broken の順で、broken は 3 行目
    mock_index.queued[("PUT", "/settings/sources")] = [
        (
            400,
            {
                "detail": "引数が正しくありません: 1 件",
                "errors": [{"path": "sources[2].enabled", "reason": "bool ではない"}],
            },
        )
    ]
    text = (
        'version: "1"\nclone: /x\nsources:\n'
        "  - id: sample\n    config: /repo/sample/dev-docs.yaml\n"
        "  - id: broken\n    config: /repo/broken/dev-docs.yaml\n    enabled: maybe\n"
    )
    settings = tmp_path / "settings.yaml"
    settings.write_text(text, encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(settings))
    # 実行
    code = main(["migrate", "--project-index", mock_index.address])
    # 検証
    error = capsys.readouterr().err
    assert code == 4
    assert "400" in error
    assert "broken: bool ではない" in error
    assert mock_index.rows == [{"id": "extra", "config": ["/repo/other/project-index.yaml"]}]
    assert settings.read_text(encoding="utf-8") == text
    assert _backups(tmp_path) == []


def test_error_when_save_unconfirmed_after_timeout(
    tmp_path: Path,
    mock_index: MockIndex,
    write_steps: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """保存の応答が制限時間を超え、再取得しても移す行が無ければ、端末の設定を書き換えずに終了コード 7 で止める（異常系）。"""
    # 準備
    write_steps("settings", "2", [EXPORT_SOURCES])
    mock_index.put_saves = False
    mock_index.put_delay_sec = 3
    monkeypatch.setattr(main_module, "PROJECT_INDEX_TIMEOUT_SEC", 1)
    settings = _write_v1(tmp_path, monkeypatch, "settings.yaml")
    # 実行
    code = main(["migrate", "--project-index", mock_index.address])
    # 検証
    error = capsys.readouterr().err
    assert code == 7
    assert "後から反映される" in error
    assert "再実行" in error
    assert settings.read_text(encoding="utf-8") == SOURCES_V1
    assert _backups(tmp_path) == []


def test_error_when_project_index_unreachable(
    tmp_path: Path,
    free_port: Callable[[], int],
    write_steps: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """project-index につながらないと、端末の設定を書き換えずに終了コード 7 で止める（異常系）。"""
    # 準備
    write_steps("settings", "2", [EXPORT_SOURCES])
    settings = _write_v1(tmp_path, monkeypatch, "settings.yaml")
    address = f"http://127.0.0.1:{free_port()}"
    # 実行
    code = main(["migrate", "--project-index", address])
    # 検証
    error = capsys.readouterr().err
    assert code == 7
    assert address in error
    assert "project-index を起動してから" in error
    assert settings.read_text(encoding="utf-8") == SOURCES_V1
    assert _backups(tmp_path) == []
