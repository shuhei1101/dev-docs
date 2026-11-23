from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "project-index-on-conflict.sh"
BRANCH = "project-index/conflict/20261123-103000-0a1b2c3"
PR_URL = "https://github.com/o/r/pull/9"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
# 受けた引数を 1 行ずつ記録し、環境変数で指定した出力と終了コードで終わる gh のスタブ
GH_STUB = """#!/bin/sh
for arg in "$@"; do echo "$arg" >> "$GH_CALLS"; done
if [ -n "$GH_STDERR" ]; then echo "$GH_STDERR" >&2; fi
if [ -n "$GH_STDOUT" ]; then echo "$GH_STDOUT"; fi
exit "${GH_EXIT:-0}"
"""


@dataclass(frozen=True)
class ConflictClone:
    """衝突したときのブランチを持つクローンと、リモート・gh のスタブ。"""

    root: Path
    remote: Path
    stub_dir: Path

    def git(self, *args: str, cwd: Path | None = None) -> str:
        """git を実行して標準出力を返却する。"""
        done = subprocess.run(
            ["git", *args],
            cwd=cwd or self.root,
            env={**os.environ, **GIT_ENV},
            check=True,
            capture_output=True,
            text=True,
        )
        return done.stdout.strip()

    def run(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        """クローンを作業ディレクトリにしてスクリプトを実行する。"""
        base = {
            **os.environ,
            **GIT_ENV,
            "PATH": f"{self.stub_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_CALLS": str(self.stub_dir / "calls"),
        }
        return subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=self.root,
            env={**base, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    def gh_calls(self) -> list[str]:
        """gh が受けた引数の並び（呼ばれていなければ空）。"""
        path = self.stub_dir / "calls"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _env(**overrides: str) -> dict[str, str]:
    """必須の環境変数を全て持つ環境変数を作る。"""
    values = {
        "PROJECT_INDEX_CONFLICT_BRANCH": BRANCH,
        "PROJECT_INDEX_TARGET_BRANCH": "develop",
        "PROJECT_INDEX_COMMIT_MESSAGE": "タグを修正する",
        "PROJECT_INDEX_SOURCE": "dev-docs",
        "PROJECT_INDEX_BASE_COMMIT": "0a1b2c3",
    }
    return {**values, **overrides}


@pytest.fixture
def clone(tmp_path: Path) -> ConflictClone:
    """`develop` と修正を 1 コミット持つ衝突したときのブランチのクローンを作る。"""
    remote = tmp_path / "remote.git"
    root = tmp_path / "clone"
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    made = ConflictClone(root=root, remote=remote, stub_dir=stub_dir)
    made.git("init", "-q", "--bare", str(remote), cwd=tmp_path)
    made.git("init", "-q", "-b", "develop", str(root), cwd=tmp_path)
    (root / "a.yaml").write_text("tags: [topic:a]\n", encoding="utf-8")
    made.git("add", "a.yaml")
    made.git("commit", "-q", "-m", "init")
    made.git("remote", "add", "origin", str(remote))
    made.git("push", "-q", "origin", "develop")
    made.git("checkout", "-q", "-b", BRANCH)
    (root / "a.yaml").write_text("tags: [topic:a, topic:b]\n", encoding="utf-8")
    made.git("commit", "-q", "-am", "タグを修正する")
    made.git("checkout", "-q", "develop")
    return made


def test_main(clone: ConflictClone) -> None:
    """プッシュして PR を作成する（正常系）。"""
    # 準備
    env = _env(GH_STDOUT=PR_URL)
    # 実行
    done = clone.run(env)
    # 検証
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == PR_URL
    assert clone.git("ls-remote", "--heads", "origin", BRANCH) != ""
    calls = clone.gh_calls()
    assert calls[:2] == ["pr", "create"]
    assert calls[calls.index("--base") + 1] == "develop"
    assert calls[calls.index("--head") + 1] == BRANCH
    assert calls[calls.index("--title") + 1] == "タグを修正する"
    assert "--label" not in calls


def test_main_when_env_missing(clone: ConflictClone) -> None:
    """必須の環境変数が無い（異常系）。"""
    # 準備
    env = _env(PROJECT_INDEX_CONFLICT_BRANCH="")
    # 実行
    done = clone.run(env)
    # 検証
    assert done.returncode == 2
    assert "PROJECT_INDEX_CONFLICT_BRANCH" in done.stderr
    assert clone.gh_calls() == []


def test_main_when_push_failed(clone: ConflictClone) -> None:
    """プッシュの失敗（異常系）。"""
    # 準備
    clone.git("remote", "remove", "origin")
    # 実行
    done = clone.run(_env(GH_STDOUT=PR_URL))
    # 検証
    assert done.returncode != 0
    assert clone.gh_calls() == []
    assert [line for line in done.stdout.splitlines() if line.startswith("https://")] == []


def test_main_when_pr_create_failed(clone: ConflictClone) -> None:
    """PR の作成の失敗（異常系）。"""
    # 準備
    env = _env(GH_STDERR="authentication required", GH_EXIT="1")
    # 実行
    done = clone.run(env)
    # 検証
    assert done.returncode == 1
    assert "authentication required" in done.stderr
    assert [line for line in done.stdout.splitlines() if line.startswith("https://")] == []
