"""テストの全件実行の workflow（.github/workflows/test.yml）の E2E テスト。本物の GitHub Actions で起動して確認する。"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

# 起動する workflow のファイル名
WORKFLOW = "test.yml"

# ログを上げる成果物の名前と、その中のファイル名
ARTIFACT = "test-log"
LOG_FILE = "test.log"

# workflow のファイルの step の名前。GitHub が追加する step（Set up job 等）は確認しない
STEPS = (
    "ブランチを取得する",
    "Node.js を入れる",
    "uv を入れる",
    "Python の依存を入れる",
    "npm の依存を入れる",
    "Chromium を入れる",
    "層の全件を回す",
    "ログを成果物に上げる",
)

# pytest の最終行の集計
PYTEST_SUMMARY = re.compile(r"^=+ .*\d+ (passed|failed).* in [\d.]+s.*=+$", re.MULTILINE)

# vitest の集計（テストの件数の行）
VITEST_SUMMARY = re.compile(r"^\s*Tests\s+.*\d+ passed.*$", re.MULTILINE)

# Playwright の集計（成功したテストの件数の行）
PLAYWRIGHT_SUMMARY = re.compile(r"^\s*\d+ passed \(.+\)$", re.MULTILINE)

# 端末の色の制御文字（vitest・Playwright が集計の行に付ける）
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# 検証用のブランチを push する前に、worktree へ適用する変更
type Mutation = Callable[[Path], None]

# 検証用のブランチを作る関数（branch_factory の fixture）
type BranchFactory = Callable[[Mutation | None], str]

# workflow を起動して、実行の ID・結論・step ごとの結論を返却する関数（workflow_runner の fixture）
type WorkflowRunner = Callable[[str, str, Mapping[str, str]], tuple[str, str, dict[str, str]]]

# 成果物の中のファイルの本文を返却する関数（artifact_reader の fixture）
type ArtifactReader = Callable[[str, str, str], str]


def _read_log(artifact_reader: ArtifactReader, run_id: str) -> str:
    """成果物のログを取得し、色の制御文字を除いた本文を返却する。"""
    return ANSI_ESCAPE.sub("", artifact_reader(run_id, ARTIFACT, LOG_FILE))


def _assert_steps(steps: Mapping[str, str], expected: Mapping[str, str]) -> None:
    """図の step が期待した結論で通り、図に無い step が skipped かを確認する。"""
    for name in STEPS:
        assert steps.get(name) == expected.get(name, "skipped"), name


def _add_failing_test(worktree: Path) -> None:
    """tests/unit/ に必ず失敗するテストを 1 件追加する。"""
    (worktree / "tests/unit/test_always_fail.py").write_text(
        '"""検証用に必ず失敗するテスト。"""\n\n\n'
        "def test_always_fail() -> None:\n"
        '    """必ず失敗する。"""\n'
        "    assert False\n",
        encoding="utf-8",
    )


def _add_silent_test(worktree: Path) -> None:
    """tests/unit/ に、何も出力せずに 60 秒待つテストを 1 件追加する。"""
    (worktree / "tests/unit/test_silent_wait.py").write_text(
        '"""検証用に何も出力せずに待つテスト。"""\n\n'
        "import time\n\n\n"
        "def test_silent_wait() -> None:\n"
        '    """何も出力せずに 60 秒待つ。"""\n'
        "    time.sleep(60)\n",
        encoding="utf-8",
    )


def _break_package_lock(worktree: Path) -> None:
    """package-lock.json を JSON として読めない内容にし、npm ci を失敗させる。"""
    (worktree / "package-lock.json").write_text("{\n", encoding="utf-8")


def test_normal(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """単体テスト（バック）の層の全件が pass して成功で終わる（正常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "backend-unit"})

    # 検証
    assert conclusion == "success"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Python の依存を入れる": "success",
            "層の全件を回す": "success",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    summary = PYTEST_SUMMARY.search(log)
    assert summary is not None
    # 手元の全件実行の skip は 0 件（2026-11-17 の計測）
    assert "skipped" not in summary[0]


def test_normal_when_backend_integration(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """結合テスト（バック）の層の全件が pass して成功で終わる（正常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "backend-integration"})

    # 検証
    assert conclusion == "success"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Python の依存を入れる": "success",
            "層の全件を回す": "success",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    summary = PYTEST_SUMMARY.search(log)
    assert summary is not None
    # 手元の全件実行の skip は 0 件（2026-11-17 の計測）
    assert "skipped" not in summary[0]


def test_normal_when_frontend_unit(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """単体テスト（フロント）の層の全件が pass して成功で終わる（正常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "frontend-unit"})

    # 検証
    assert conclusion == "success"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "npm の依存を入れる": "success",
            "層の全件を回す": "success",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    summary = VITEST_SUMMARY.search(log)
    assert summary is not None
    # 手元の全件実行の skip は 0 件（2026-11-17 の計測）
    assert "skipped" not in summary[0]


def test_normal_when_frontend_integration(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """結合テスト（フロント）の層の全件が pass して成功で終わる（正常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "frontend-integration"})

    # 検証
    assert conclusion == "success"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "npm の依存を入れる": "success",
            "Chromium を入れる": "success",
            "層の全件を回す": "success",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    assert PLAYWRIGHT_SUMMARY.search(log) is not None
    # 手元の全件実行の skip は 0 件（2026-11-17 の計測）
    assert re.search(r"^\s*\d+ skipped$", log, re.MULTILINE) is None


def test_normal_when_paths_given(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """指定した結合テストだけを回し、成功で終わる（正常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, steps = workflow_runner(
        WORKFLOW, branch, {"layer": "backend-integration", "paths": "tests/integration/plugin/"}
    )

    # 検証
    assert conclusion == "success"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Python の依存を入れる": "success",
            "層の全件を回す": "success",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    assert "tests/integration/plugin/" in log
    assert "tests/integration/server/" not in log


def test_error_when_tests_fail(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """層の全件に fail があり、ログを上げて失敗で終わる（異常系）。"""
    # 準備
    branch = branch_factory(_add_failing_test)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "backend-unit"})

    # 検証
    assert conclusion == "failure"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Python の依存を入れる": "success",
            "層の全件を回す": "failure",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    assert "test_always_fail" in log
    summary = PYTEST_SUMMARY.search(log)
    assert summary is not None
    assert "failed" in summary[0]


def test_error_when_output_stalls(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, artifact_reader: ArtifactReader
) -> None:
    """出力が上限の時間を超えて変わらず、テストを止めてログを上げ、失敗で終わる（異常系）。"""
    # 準備
    branch = branch_factory(_add_silent_test)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "backend-unit"})

    # 検証
    assert conclusion == "failure"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Python の依存を入れる": "success",
            "層の全件を回す": "failure",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    assert "出力が 7 秒変わらなかったため、テストを止めた" in log


def test_error_when_setup_fails(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner
) -> None:
    """依存の導入に失敗し、層の全件を回さずにログを上げて失敗で終わる（異常系）。"""
    # 準備
    branch = branch_factory(_break_package_lock)

    # 実行
    _, conclusion, steps = workflow_runner(WORKFLOW, branch, {"layer": "frontend-unit"})

    # 検証
    assert conclusion == "failure"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "npm の依存を入れる": "failure",
            "ログを成果物に上げる": "success",
        },
    )


@pytest.mark.parametrize(
    ("inputs", "expected_steps", "reason"),
    [
        pytest.param(
            {"layer": "backend-integration", "paths": "tests/integration/frontend/"},
            {"uv を入れる": "success", "Python の依存を入れる": "success"},
            "paths の値が層の結合テストのフォルダの外（tests/integration/frontend/ は frontend-integration の層）: tests/integration/frontend/",
            id="other-layer-folder",
        ),
        pytest.param(
            {"layer": "backend-unit", "paths": "tests/integration/"},
            {"uv を入れる": "success", "Python の依存を入れる": "success"},
            "paths は結合テストの層でだけ指定できる: layer=backend-unit",
            id="not-integration-layer",
        ),
        pytest.param(
            {"layer": "frontend-integration", "paths": "tests/integration/frontend/../server/"},
            {
                "npm の依存を入れる": "success",
                "Chromium を入れる": "success",
            },
            "paths の値が .. を含む: tests/integration/frontend/../server/",
            id="parent-directory",
        ),
        pytest.param(
            {"layer": "backend-integration", "paths": "tests/integration/plugin/;ls"},
            {"uv を入れる": "success", "Python の依存を入れる": "success"},
            "paths に許可しない文字がある（英数字・_・.・/・-・空白だけを許可する）: tests/integration/plugin/;ls",
            id="forbidden-character",
        ),
    ],
)
def test_error_when_paths_outside_layer(
    branch_factory: BranchFactory,
    workflow_runner: WorkflowRunner,
    artifact_reader: ArtifactReader,
    inputs: Mapping[str, str],
    expected_steps: Mapping[str, str],
    reason: str,
) -> None:
    """paths に層の結合テストのフォルダの外のパスを指定し、テストを回さずに失敗で終わる（異常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, steps = workflow_runner(WORKFLOW, branch, inputs)

    # 検証
    assert conclusion == "failure"
    _assert_steps(
        steps,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            **expected_steps,
            "層の全件を回す": "failure",
            "ログを成果物に上げる": "success",
        },
    )
    log = _read_log(artifact_reader, run_id)
    assert reason in log
    assert PYTEST_SUMMARY.search(log) is None
    assert PLAYWRIGHT_SUMMARY.search(log) is None
