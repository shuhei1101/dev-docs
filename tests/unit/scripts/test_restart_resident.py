from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "dev-docs-restart-resident.sh"
# 呼ばれた引数を記録して、環境変数で指定した終了コードで終わるスタブ
STUB = """#!/bin/sh
echo "$(basename "$0") $*" >> "$STUB_CALLS"
exit "${{{var}:-0}}"
"""
GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


@dataclass(frozen=True)
class ResidentRepo:
    """スクリプトを配置した一時リポジトリと、スタブ・状態のフォルダ。"""

    root: Path
    stub_dir: Path
    state_dir: Path

    def _git(self, *args: str) -> str:
        """一時リポジトリで git を実行して標準出力を返却する。"""
        env = {**os.environ, **GIT_ENV}
        done = subprocess.run(
            ["git", *args], cwd=self.root, env=env, check=True, capture_output=True, text=True
        )
        return done.stdout.strip()

    def commit(self, files: dict[str, str]) -> str:
        """ファイルを書いて commit し、その SHA を返却する。"""
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self._git("add", "--", *files)
        self._git("commit", "-q", "-m", "test")
        return self._git("rev-parse", "HEAD")

    def write_record(self, sha: str) -> None:
        """前回起動し直した commit の記録を書く。"""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "restarted-commit").write_text(f"{sha}\n", encoding="utf-8")

    def record(self) -> str | None:
        """記録の 1 行目を返却する。記録が無ければ None。"""
        path = self.state_dir / "restarted-commit"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").splitlines()[0]

    def calls(self) -> list[str]:
        """スタブが呼ばれた順の `{コマンド} {引数}` を返却する。"""
        path = self.stub_dir / "calls"
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()

    def run(self, *, uv_exit: int = 0, systemctl_exit: int = 0) -> subprocess.CompletedProcess[str]:
        """スタブを PATH の先頭に置いてスクリプトを実行する。"""
        env = {
            **os.environ,
            "PATH": f"{self.stub_dir}{os.pathsep}{os.environ['PATH']}",
            "DEV_DOCS_STATE_DIR": str(self.state_dir),
            "STUB_CALLS": str(self.stub_dir / "calls"),
            "UV_EXIT": str(uv_exit),
            "SYSTEMCTL_EXIT": str(systemctl_exit),
        }
        script = self.root / "scripts" / SCRIPT.name
        return subprocess.run(
            ["bash", str(script)], cwd=self.root, env=env, capture_output=True, text=True
        )


@pytest.fixture
def resident_repo(tmp_path: Path) -> ResidentRepo:
    """スクリプトを `scripts/` に配置した一時リポジトリと、`uv`・`systemctl` のスタブを用意する。"""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    # スクリプトがまだ無いときは配置せず、実行が失敗する
    if SCRIPT.exists():
        shutil.copy(SCRIPT, root / "scripts" / SCRIPT.name)
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    for name, var in (("uv", "UV_EXIT"), ("systemctl", "SYSTEMCTL_EXIT")):
        stub = stub_dir / name
        stub.write_text(STUB.format(var=var), encoding="utf-8")
        stub.chmod(0o755)
    return ResidentRepo(root=root, stub_dir=stub_dir, state_dir=tmp_path / "state")


# --- main ---


def test_main_when_no_record(resident_repo: ResidentRepo) -> None:
    """記録が無いときは依存をそろえて起動し直し、記録を HEAD にする（正常系）。"""
    # 準備
    head = resident_repo.commit({"src/app.py": "a = 1\n"})

    # 実行
    result = resident_repo.run()

    # 検証
    assert result.returncode == 0
    assert resident_repo.calls() == [
        "uv sync --frozen",
        "systemctl --user restart dev-docs.service",
    ]
    assert resident_repo.record() == head


def test_main_when_runtime_changed(resident_repo: ResidentRepo) -> None:
    """実行時に参照するファイルが変わったときは依存をそろえて起動し直す（正常系）。"""
    # 準備
    previous = resident_repo.commit({"src/app.py": "a = 1\n"})
    head = resident_repo.commit({"src/app.py": "a = 2\n"})
    resident_repo.write_record(previous)

    # 実行
    result = resident_repo.run()

    # 検証
    assert result.returncode == 0
    assert resident_repo.calls() == [
        "uv sync --frozen",
        "systemctl --user restart dev-docs.service",
    ]
    assert resident_repo.record() == head


def test_main_when_runtime_unchanged(resident_repo: ResidentRepo) -> None:
    """実行時に参照するファイルが変わっていないときは起動し直さずに記録だけ進める（正常系）。"""
    # 準備
    previous = resident_repo.commit({"src/app.py": "a = 1\n"})
    head = resident_repo.commit({"docs/guide.md": "# guide\n"})
    resident_repo.write_record(previous)

    # 実行
    result = resident_repo.run()

    # 検証
    assert result.returncode == 0
    assert resident_repo.calls() == []
    assert resident_repo.record() == head


def test_main_when_record_unknown(resident_repo: ResidentRepo) -> None:
    """記録の commit が見つからないときは依存をそろえて起動し直す（異常系）。"""
    # 準備
    head = resident_repo.commit({"src/app.py": "a = 1\n"})
    resident_repo.write_record("0123456789abcdef0123456789abcdef01234567")

    # 実行
    result = resident_repo.run()

    # 検証
    assert result.returncode == 0
    assert resident_repo.calls() == [
        "uv sync --frozen",
        "systemctl --user restart dev-docs.service",
    ]
    assert resident_repo.record() == head


def test_main_when_sync_failed(resident_repo: ResidentRepo) -> None:
    """依存の入れ直しが失敗したときは起動し直さず、記録を作らない（異常系）。"""
    # 準備
    resident_repo.commit({"src/app.py": "a = 1\n"})

    # 実行
    result = resident_repo.run(uv_exit=1)

    # 検証
    assert result.returncode != 0
    assert resident_repo.calls() == ["uv sync --frozen"]
    assert resident_repo.record() is None


def test_main_when_restart_failed(resident_repo: ResidentRepo) -> None:
    """起動し直しが失敗したときは記録を前の commit のまま残す（異常系）。"""
    # 準備
    previous = resident_repo.commit({"uv.lock": "version = 1\n"})
    resident_repo.commit({"uv.lock": "version = 2\n"})
    resident_repo.write_record(previous)

    # 実行
    result = resident_repo.run(systemctl_exit=1)

    # 検証
    assert result.returncode != 0
    assert resident_repo.calls() == [
        "uv sync --frozen",
        "systemctl --user restart dev-docs.service",
    ]
    assert resident_repo.record() == previous
