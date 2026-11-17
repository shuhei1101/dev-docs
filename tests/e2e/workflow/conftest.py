"""workflow の E2E テストで共通に使用する fixture。検証用のブランチを push し、gh で workflow を起動して結果を取得する。"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

import pytest

# リポジトリの直下
REPO_ROOT = Path(__file__).resolve().parents[3]

# 実行を待つ上限の秒数。ジョブの timeout-minutes を指定しないため、GitHub Actions の 1 ジョブの上限（360 分）に、ランナーの割り当ての待ちの 5 分を加えた値
_WATCH_SEC = (360 + 5) * 60

# git・gh の 1 回の操作を待つ上限の秒数
_COMMAND_SEC = 120

# 起動した実行を API で参照できるまで試す回数と間隔の秒数。テスト実行方法の run_runner と同じ値
_VISIBLE_TRIES = 10
_VISIBLE_INTERVAL_SEC = 1

# gh workflow run の出力の実行の URL
_RUN_URL = re.compile(r"https://\S+/actions/runs/(\d+)")

# 検証用のブランチを push する前に、worktree へ適用する変更
type Mutation = Callable[[Path], None]


def _run(
    args: list[str], cwd: Path, *, timeout: int = _COMMAND_SEC, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """コマンドを起動して終わるまで待つ。check が真なら、0 以外で終われば例外を送出する。"""
    # 引数は配列で指定し、シェルを経由しない
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=check
    )


@pytest.fixture
def branch_factory(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[Callable[[Mutation | None], str]]:
    """今の HEAD から検証用のブランチを作って push する関数を返却し、テストの後にブランチと worktree を削除する。"""
    created: list[tuple[str, Path]] = []

    def _create(mutation: Mutation | None = None) -> str:
        # テストの関数名と時刻を含め、同時に回したテストと重ならない名前にする
        stamp = time.strftime("%Y%m%d%H%M%S")
        branch = f"test-workflow/{request.node.name}-{stamp}-{len(created)}"
        worktree = tmp_path / f"worktree-{len(created)}"
        _run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"], REPO_ROOT)
        created.append((branch, worktree))
        # 変更を適用するフローだけ、変更を commit してから push する
        if mutation is not None:
            mutation(worktree)
            _run(["git", "add", "--all"], worktree)
            _run(
                [
                    "git",
                    "commit",
                    "--no-verify",
                    "--message",
                    f"test: {request.node.name} の検証用の変更",
                ],
                worktree,
            )
        _run(["git", "push", "--no-verify", "origin", f"HEAD:refs/heads/{branch}"], worktree)
        return branch

    yield _create
    # テストが失敗しても、作った順の逆にブランチと worktree を削除する
    for branch, worktree in reversed(created):
        _run(["git", "push", "--no-verify", "origin", "--delete", branch], REPO_ROOT, check=False)
        _run(["git", "worktree", "remove", "--force", str(worktree)], REPO_ROOT, check=False)


def _dispatch(workflow: str, branch: str, inputs: Mapping[str, str]) -> str:
    """workflow を workflow_dispatch で起動し、出力の URL の末尾から実行の ID を返却する。"""
    fields = [arg for name, value in inputs.items() for arg in ("-f", f"{name}={value}")]
    result = _run(["gh", "workflow", "run", workflow, "--ref", branch, *fields], REPO_ROOT)
    match = _RUN_URL.search(result.stdout + result.stderr)
    assert match is not None, (
        f"gh workflow run の出力に実行の URL がありません: {result.stdout}{result.stderr}"
    )
    return match[1]


def _wait_visible(run_id: str) -> None:
    """起動直後の実行を API で参照できるまで待ち、決めた回数で参照できなければテストを失敗にする。"""
    for _ in range(_VISIBLE_TRIES):
        result = _run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}?exclude_pull_requests=true",
            ],
            REPO_ROOT,
            check=False,
        )
        # 参照できた: gh run watch を呼べる
        if result.returncode == 0:
            return
        # まだ参照できない: 間隔を空けてもう一度試す
        time.sleep(_VISIBLE_INTERVAL_SEC)
    pytest.fail(f"実行 {run_id} を {_VISIBLE_TRIES * _VISIBLE_INTERVAL_SEC} 秒参照できません")


def _watch(run_id: str) -> tuple[str, dict[str, str]]:
    """実行が終わるまで待ち、実行の結論と step の名前ごとの結論を返却する。"""
    # 異常系のフローは 0 以外で終わるため、終了コードでは失敗にせず、結論で確認する
    _run(
        ["gh", "run", "watch", run_id, "--exit-status"], REPO_ROOT, timeout=_WATCH_SEC, check=False
    )
    result = _run(["gh", "run", "view", run_id, "--json", "conclusion,jobs"], REPO_ROOT)
    data = json.loads(result.stdout)
    steps = {
        str(step["name"]): str(step["conclusion"]) for job in data["jobs"] for step in job["steps"]
    }
    return str(data["conclusion"]), steps


@pytest.fixture
def workflow_runner() -> Callable[[str, str, Mapping[str, str]], tuple[str, str, dict[str, str]]]:
    """workflow を起動して終わるまで待ち、実行の ID・結論・step ごとの結論を返却する関数を返却する。"""

    def _start(
        workflow: str, branch: str, inputs: Mapping[str, str]
    ) -> tuple[str, str, dict[str, str]]:
        run_id = _dispatch(workflow, branch, inputs)
        _wait_visible(run_id)
        conclusion, steps = _watch(run_id)
        return run_id, conclusion, steps

    return _start


@pytest.fixture
def artifact_reader(tmp_path: Path) -> Callable[[str, str, str], str]:
    """実行の成果物を一時フォルダへ取得し、中のファイルの本文を返却する関数を返却する。"""

    def _read(run_id: str, artifact: str, file_name: str) -> str:
        destination = tmp_path / f"artifact-{run_id}"
        _run(["gh", "run", "download", run_id, "-n", artifact, "-D", str(destination)], REPO_ROOT)
        return (destination / file_name).read_text(encoding="utf-8")

    return _read
