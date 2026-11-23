from __future__ import annotations

import os
import subprocess
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
SCRIPT_ENV = {
    "PROJECT_INDEX_CONFLICT_BRANCH": BRANCH,
    "PROJECT_INDEX_TARGET_BRANCH": "develop",
    "PROJECT_INDEX_COMMIT_MESSAGE": "タグを修正する",
    "PROJECT_INDEX_SOURCE": "dev-docs",
    "PROJECT_INDEX_BASE_COMMIT": "0a1b2c3",
}


def _git(cwd: Path, *args: str) -> str:
    """git を実行して標準出力を返却する。"""
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **GIT_ENV},
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _run(tmp_path: Path, **gh: str) -> subprocess.CompletedProcess[str]:
    """クローンを作業ディレクトリにして、project-index と同じく環境変数でスクリプトを実行する。"""
    env = {
        **os.environ,
        **GIT_ENV,
        **SCRIPT_ENV,
        **gh,
        "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "GH_CALLS": str(tmp_path / "calls"),
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path / "clone",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """`develop` と、修正を 1 コミット持つ衝突したときのブランチを持つクローンと、gh のスタブを作る。"""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    bare = tmp_path / "remote.git"
    root = tmp_path / "clone"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    _git(tmp_path, "init", "-q", "-b", "develop", str(root))
    (root / "n1.yaml").write_text("tags: [topic:a]\n", encoding="utf-8")
    _git(root, "add", "n1.yaml")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "develop")
    _git(root, "checkout", "-q", "-b", BRANCH)
    (root / "n1.yaml").write_text("tags: [topic:a, topic:b]\n", encoding="utf-8")
    _git(root, "commit", "-q", "-am", "タグを修正する")
    _git(root, "checkout", "-q", "develop")
    return bare


def test_normal(tmp_path: Path, remote: Path) -> None:
    """ブランチをプッシュして PR を作成し、PR の URL を出力する（正常系）。"""
    # 準備
    gh = {"GH_STDOUT": PR_URL}
    # 実行
    done = _run(tmp_path, **gh)
    # 検証
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == PR_URL
    assert _git(remote, "branch", "--list", BRANCH) != ""
    calls = (tmp_path / "calls").read_text(encoding="utf-8").splitlines()
    assert calls[:2] == ["pr", "create"]
    assert calls[calls.index("--base") + 1] == "develop"
    assert calls[calls.index("--head") + 1] == BRANCH
    assert calls[calls.index("--title") + 1] == "タグを修正する"
    assert "--label" not in calls


def test_error_when_pr_create_failed(tmp_path: Path, remote: Path) -> None:
    """`gh` が失敗したら、標準エラー出力に理由を出して 0 以外で終わる（異常系）。"""
    # 準備
    gh = {"GH_STDERR": "authentication required", "GH_EXIT": "1"}
    # 実行
    done = _run(tmp_path, **gh)
    # 検証
    assert done.returncode != 0
    assert "authentication required" in done.stderr
    assert not any(line.startswith("https://") for line in done.stdout.splitlines())
