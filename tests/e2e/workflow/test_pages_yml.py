"""公開ページの配信の workflow（.github/workflows/pages.yml）の E2E テスト。本物の GitHub Actions の実行を確認する。"""

from __future__ import annotations

import json
import subprocess
import tarfile
from collections.abc import Callable, Mapping
from pathlib import Path

# 起動する workflow のファイル名
WORKFLOW = "pages.yml"

# 公開ページを上げる成果物の名前と、その中の tar のファイル名
ARTIFACT = "github-pages"
ARTIFACT_TAR = "artifact.tar"

# job の ID
BUILD_JOB = "build"
DEPLOY_JOB = "deploy"

# job build の step の名前。GitHub が追加する step（Set up job 等）は確認しない
BUILD_STEPS = (
    "ブランチを取得する",
    "Node.js を入れる",
    "uv を入れる",
    "Pages の設定を読み込む",
    "公開の文書を 1 枚の HTML にまとめる",
    "成果物に YAML が無いことを確認する",
    "成果物を Pages 用に上げる",
)

# job deploy の step の名前
DEPLOY_STEPS = ("GitHub Pages へ配信する",)

# 検証用のブランチで、公開ドキュメントの分類に無い値にする files.yml の行（先頭の 1 行だけを置き換える）
GUIDE_FILES = "docs/guide/files.yml"
VALID_CATEGORY_LINE = "  category: はじめに\n"
INVALID_CATEGORY_LINE = "  category: 存在しない分類\n"

# 検証用のブランチで、1 枚の HTML の出力の後に YAML のファイルも書き出すように変える build_pages.py の行
BUILD_SCRIPT = "scripts/build_pages.py"
COPY_HTML_LINE = "            shutil.copyfile(workdir / OUTPUT_HTML, out / OUTPUT_HTML)\n"
LEAK_YAML_LINE = '            (out / "leak.yaml").write_text("leak: true\\n", encoding="utf-8")\n'

# リポジトリの直下
REPO_ROOT = Path(__file__).resolve().parents[3]

# gh の 1 回の操作を待つ上限の秒数。conftest の git・gh の 1 回の操作と同じ値
_COMMAND_SEC = 120

# 検証用のブランチを push する前に、worktree へ適用する変更
type Mutation = Callable[[Path], None]

# 検証用のブランチを作る関数（branch_factory の fixture）
type BranchFactory = Callable[[Mutation | None], str]

# workflow を起動して、実行の ID・結論・step ごとの結論を返却する関数（workflow_runner の fixture）
type WorkflowRunner = Callable[[str, str, Mapping[str, str]], tuple[str, str, dict[str, str]]]

# job の ID ごとの、job の結論と step の名前ごとの結論
type Jobs = dict[str, tuple[str, dict[str, str]]]


def _gh(args: list[str]) -> str:
    """gh を起動して終わるまで待ち、標準出力を返却する。0 以外で終われば例外を送出する。"""
    # 引数は配列で指定し、シェルを経由しない
    result = subprocess.run(
        ["gh", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=_COMMAND_SEC,
        check=True,
    )
    return result.stdout


def _view_run(run_id: str) -> tuple[str, Jobs]:
    """実行の結論と、job の ID ごとの job の結論・step ごとの結論を返却する。"""
    data = json.loads(_gh(["run", "view", run_id, "--json", "conclusion,jobs"]))
    jobs: Jobs = {
        str(job["name"]): (
            str(job["conclusion"]),
            {str(step["name"]): str(step["conclusion"]) for step in job["steps"]},
        )
        for job in data["jobs"]
    }
    return str(data["conclusion"]), jobs


def _latest_develop_push_run() -> str:
    """develop への push で起動した、直近の完了した実行の ID を返却する。"""
    runs = json.loads(
        _gh(
            [
                "run",
                "list",
                "--workflow",
                WORKFLOW,
                "--branch",
                "develop",
                "--event",
                "push",
                "--status",
                "completed",
                "--limit",
                "1",
                "--json",
                "databaseId",
            ]
        )
    )
    assert runs, "develop への push で起動した完了した実行がありません"
    return str(runs[0]["databaseId"])


def _artifact_names(run_id: str, destination: Path) -> list[str]:
    """成果物 github-pages を取得し、その中の artifact.tar に入っているファイルの名前を返却する。"""
    _gh(["run", "download", run_id, "-n", ARTIFACT, "-D", str(destination)])
    with tarfile.open(destination / ARTIFACT_TAR) as archive:
        return archive.getnames()


def _assert_steps(
    steps: Mapping[str, str], names: tuple[str, ...], expected: Mapping[str, str]
) -> None:
    """図の step が期待した結論で通り、図に無い step が skipped かを確認する。"""
    for name in names:
        assert steps.get(name) == expected.get(name, "skipped"), name


def _break_guide_category(worktree: Path) -> None:
    """files.yml の公開ドキュメントの先頭の行の分類を、分類に無い値にする。"""
    path = worktree / GUIDE_FILES
    text = path.read_text(encoding="utf-8")
    assert VALID_CATEGORY_LINE in text
    path.write_text(text.replace(VALID_CATEGORY_LINE, INVALID_CATEGORY_LINE, 1), encoding="utf-8")


def _leak_yaml_into_site(worktree: Path) -> None:
    """build_pages.py が 1 枚の HTML の出力の後に、出力のフォルダへ YAML のファイルも書き出すようにする。"""
    path = worktree / BUILD_SCRIPT
    text = path.read_text(encoding="utf-8")
    assert COPY_HTML_LINE in text
    path.write_text(text.replace(COPY_HTML_LINE, COPY_HTML_LINE + LEAK_YAML_LINE), encoding="utf-8")


def test_normal() -> None:
    """develop への push で公開ページをまとめて配信し、成功で終わる（正常系）。"""
    # 準備
    run_id = _latest_develop_push_run()

    # 実行
    conclusion, jobs = _view_run(run_id)

    # 検証
    assert conclusion == "success"
    build_conclusion, build_steps = jobs[BUILD_JOB]
    assert build_conclusion == "success"
    _assert_steps(build_steps, BUILD_STEPS, dict.fromkeys(BUILD_STEPS, "success"))
    deploy_conclusion, deploy_steps = jobs[DEPLOY_JOB]
    assert deploy_conclusion == "success"
    _assert_steps(deploy_steps, DEPLOY_STEPS, dict.fromkeys(DEPLOY_STEPS, "success"))


def test_normal_when_not_develop(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner, tmp_path: Path
) -> None:
    """develop 以外のブランチで起動し、まとめて上げるまでを実行して配信を飛ばし、成功で終わる（正常系）。"""
    # 準備
    branch = branch_factory(None)

    # 実行
    run_id, conclusion, _ = workflow_runner(WORKFLOW, branch, {})

    # 検証
    assert conclusion == "success"
    _, jobs = _view_run(run_id)
    build_conclusion, build_steps = jobs[BUILD_JOB]
    assert build_conclusion == "success"
    _assert_steps(build_steps, BUILD_STEPS, dict.fromkeys(BUILD_STEPS, "success"))
    deploy_conclusion, _ = jobs[DEPLOY_JOB]
    assert deploy_conclusion == "skipped"
    assert "./index.html" in _artifact_names(run_id, tmp_path)


def test_error_when_build_fails(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner
) -> None:
    """公開の文書をまとめる処理が失敗し、上げずに失敗で終わる（異常系）。"""
    # 準備
    branch = branch_factory(_break_guide_category)

    # 実行
    run_id, conclusion, _ = workflow_runner(WORKFLOW, branch, {})

    # 検証
    assert conclusion == "failure"
    _, jobs = _view_run(run_id)
    build_conclusion, build_steps = jobs[BUILD_JOB]
    assert build_conclusion == "failure"
    _assert_steps(
        build_steps,
        BUILD_STEPS,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Pages の設定を読み込む": "success",
            "公開の文書を 1 枚の HTML にまとめる": "failure",
        },
    )
    deploy_conclusion, _ = jobs[DEPLOY_JOB]
    assert deploy_conclusion == "skipped"


def test_error_when_yaml_in_site(
    branch_factory: BranchFactory, workflow_runner: WorkflowRunner
) -> None:
    """まとめた成果物に YAML のファイルがあり、上げずに失敗で終わる（異常系）。"""
    # 準備
    branch = branch_factory(_leak_yaml_into_site)

    # 実行
    run_id, conclusion, _ = workflow_runner(WORKFLOW, branch, {})

    # 検証
    assert conclusion == "failure"
    _, jobs = _view_run(run_id)
    build_conclusion, build_steps = jobs[BUILD_JOB]
    assert build_conclusion == "failure"
    _assert_steps(
        build_steps,
        BUILD_STEPS,
        {
            "ブランチを取得する": "success",
            "Node.js を入れる": "success",
            "uv を入れる": "success",
            "Pages の設定を読み込む": "success",
            "公開の文書を 1 枚の HTML にまとめる": "success",
            "成果物に YAML が無いことを確認する": "failure",
        },
    )
    deploy_conclusion, _ = jobs[DEPLOY_JOB]
    assert deploy_conclusion == "skipped"
