from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import Locator, Page, expect

TEMPLATES = Path(__file__).parents[3] / "templates"
FILES_SCHEMA = TEMPLATES / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
SYNC_ZERO = {"missing_refs": 0, "unindexed_files": 0, "missing_body_files": 0}
TOOL_COUNT = 7
FILES_REQUIRED = "'files' is a required property"
SETUP_PROMPT = "/dev-docs:setup {path}"
MARKDOWN_FILES = {
    "docs/a.md": "# A\n\nA の説明。\n",
    "docs/b.md": "# B\n\nB の説明。\n",
}
UNMIGRATABLE_CONFIG = """\
version: "1"
name: notes
documents:
  - id: docs
    type: markdown
    paths: [docs/**/*.md]
    schema: schemas/files.schema.yaml
    defaults:
      - paths: [docs/**]
        tags: [doc]
"""
DESIGN_SCHEMA = """\
type: object
properties:
  id: {type: string}
  name: {type: string}
  implementation: {type: string}
required: [id, name]
"""
CANDIDATES_CONFIG = """\
version: "3"
name: sample
documents:
  - id: design
    paths: [design/*.yaml]
    schema: schemas/design.schema.yaml
  - id: src
    paths: [src/files.yaml]
    schema: schemas/files.schema.yaml
    records: files
    body_file: path
"""
IMPLEMENTATION_QUESTION = r"実装のパス|設計書の種類"
IMPLEMENTATION_ANSWER = "種類 design、キー implementation"
SCHEMA_LINE = (
    "# yaml-language-server: $schema="
    "https://raw.githubusercontent.com/shuhei1101/dev-docs/v{version}/schemas/dev-docs.schema.json\n"
)
NOTES_CONFIG = """\
version: "3"
name: notes
description: メモの配信元
documents:
  - id: files
    paths: [files.yaml]
    title: ファイル
    schema: schemas/files.schema.yaml
    records: files
    body_file: path
"""
MISMATCH_CONFIG = """\
version: "3"
name: mismatch
documents:
  - id: docs
    paths: [files.yaml]
    schema: schemas/files.schema.yaml
    records: files
    body_file: path
"""
MISMATCH_SCHEMA = "type: object\nproperties:\n  files: {type: array}\nrequired: [files]\n"
NOTES_FILES = """\
files:
  - path: docs/a.md
    name: A
    description: A の説明
  - path: docs/b.md
    name: B
    description: B の説明
    tags: [memo]
"""


def _registered_files() -> dict[str, str]:
    """管理用の YAML の行を持つ、登録済みの配信元のファイル一式を返す。"""
    return {
        "dev-docs.yaml": NOTES_CONFIG,
        "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
        "files.yaml": NOTES_FILES,
        **MARKDOWN_FILES,
    }


def _rows(load_yaml_file: Callable[[Path], Any], folder: Path) -> dict[str, dict[str, Any]]:
    """管理用の YAML の行を、パスをキーにして集める。"""
    return {row["path"]: row for row in load_yaml_file(folder / "files.yaml")["files"]}


def test_normal(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    list_mcp_tools: Callable[..., list[str]],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """フォルダを配信元として端末の設定に並べ、文書の MCP で読めるようにする（正常系）。"""
    # 準備
    clone = make_clone()
    served = serve(clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    sample = make_source("sample")
    tools_before = list_mcp_tools(served.port)
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(path=sample.folder), cwd=sample.folder)
    # 検証
    rows = load_yaml_file(served.settings)["sources"]
    checked = served.call_admin("check_project", path=str(sample.folder), format="json")
    described = served.call("describe", cwd=str(sample.folder))
    assert not run.result["is_error"]
    assert len(rows) == 1
    assert Path(rows[0]["config"][0]) == sample.folder / "dev-docs.yaml"
    assert rows[0]["scope"]["write"] == [str(sample.folder)]
    assert rows[0]["scope"]["read"] == [f"{sample.folder}/**"]
    assert checked.data.get("violations", []) == []
    assert checked.data["sync"] == SYNC_ZERO
    assert "| sample | write" in described.text
    assert len(tools_before) == TOOL_COUNT
    assert list_mcp_tools(served.port) == tools_before
    assert "sample" in run.text
    assert "|" in run.text


def test_normal_when_non_yaml_range(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
    schema_errors: Callable[[Path, Any], list[str]],
) -> None:
    """YAML でない範囲を、`dev-docs.yaml` と管理用の YAML を作って配信元に加える（正常系）。"""
    # 準備
    clone = make_clone()
    served = serve(clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    # ベンダーのコードの Markdown は、除外の条件に当たるため行を作らない
    notes = make_source("notes", {**MARKDOWN_FILES, "docs/vendor/lib.md": "# lib\n"})
    # `.git`・`node_modules`・`.claude/worktrees` の下のファイルは範囲に入れない
    for ignored in (
        "node_modules/pkg/README.md",
        ".claude/worktrees/x/memo.md",
        ".claude/worktrees/wt/docs/a.md",
    ):
        (notes.folder / ignored).parent.mkdir(parents=True, exist_ok=True)
        (notes.folder / ignored).write_text("# 除く\n", encoding="utf-8")
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(path=notes.folder), cwd=notes.folder)
    # 検証
    managed = [
        path
        for path in notes.folder.rglob("files.yaml")
        if "node_modules" not in path.parts and ".claude" not in path.parts
    ]
    loaded = load_yaml_file(managed[0])
    config_text = (notes.folder / "dev-docs.yaml").read_text(encoding="utf-8")
    config = load_yaml_file(notes.folder / "dev-docs.yaml")
    paths = [row["path"] for row in loaded["files"]]
    found = served.call("search_docs", cwd=str(notes.folder), view="ids", format="json")
    assert not run.result["is_error"]
    assert config_text.startswith(SCHEMA_LINE.format(version=clone.version))
    assert all("type" not in row for row in config["documents"])
    assert len(managed) == 1
    assert sorted(Path(path).name for path in paths) == ["a.md", "b.md"]
    assert all(row.get("name") for row in loaded["files"])
    assert not any("node_modules" in path or ".claude" in path for path in paths)
    assert not any("vendor" in path for path in paths)
    assert schema_errors(FILES_SCHEMA, loaded) == []
    assert len(found.data["items"]) == len(MARKDOWN_FILES)
    assert not any(FILES_REQUIRED in note for note in found.data.get("notes", []))


def test_normal_when_rerun(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    add_worktree: Callable[..., Path],
    serve: Callable[..., Any],
    run_git: Callable[..., str],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """範囲のファイルの追加・削除・改名を、管理用の YAML の行に合わせる（正常系）。"""
    # 準備
    clone = make_clone()
    notes = make_source("notes", _registered_files())
    notes.scope_write = [notes.folder]
    served = serve(notes, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    (notes.folder / "docs" / "c.md").write_text("# C\n\nC の説明。\n", encoding="utf-8")
    run_git(notes.folder, "add", "-A")
    run_git(notes.folder, "rm", "-q", "docs/a.md")
    run_git(notes.folder, "mv", "docs/b.md", "docs/d.md")
    run_git(notes.folder, "commit", "-m", "追加・削除・改名")
    # Git の配信元のクローン本体には書けないため、ワークツリーで path を省いて実行する
    worktree = add_worktree(notes.folder, "x")
    # 実行
    run = claude_home.run("/dev-docs:setup", cwd=worktree)
    # 検証
    rows = _rows(load_yaml_file, worktree)
    checked = served.call_admin("check_project", path=str(worktree), format="json")
    assert not run.result["is_error"]
    assert sorted(rows) == ["docs/c.md", "docs/d.md"]
    assert rows["docs/d.md"]["name"] == "B"
    assert rows["docs/d.md"]["description"] == "B の説明"
    assert rows["docs/d.md"]["tags"] == ["memo"]
    assert not any("scope" in text for text in run.question_texts)
    assert checked.data["sync"] == SYNC_ZERO


def test_normal_when_rerun_outside_git(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """Git 管理外の配信元は、内容のハッシュで改名を見つけて行のパスを直す（正常系）。"""
    # 準備
    clone = make_clone()
    notes = make_source("notes", _registered_files(), git=False)
    notes.scope_write = [notes.folder]
    served = serve(notes, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    (notes.folder / "docs" / "b.md").rename(notes.folder / "docs" / "e.md")
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(path=notes.folder), cwd=notes.folder)
    # 検証
    rows = _rows(load_yaml_file, notes.folder)
    assert not run.result["is_error"]
    assert sorted(rows) == ["docs/a.md", "docs/e.md"]
    assert rows["docs/e.md"]["name"] == "B"
    assert rows["docs/e.md"]["description"] == "B の説明"
    assert rows["docs/e.md"]["tags"] == ["memo"]


def test_error_when_source_config_invalid(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
) -> None:
    """配信元の設定が検証に通らないと、違反を示して止まり、端末の設定を書き換えない（異常系）。"""
    # 準備
    clone = make_clone()
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, git=False)
    served = serve(sample, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    before = served.settings.read_bytes()
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(path=broken.folder), cwd=broken.folder)
    # 検証
    assert served.settings.read_bytes() == before
    assert served.get("/_api/sources/sample/docs").status_code == 200
    assert "documents[0].paths" in run.text


def test_error_when_records_schema_mismatch(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
) -> None:
    """records の行のスキーマが行の項目を定めないと、違反を示して止まり、端末の設定を書き換えない（異常系）。"""
    # 準備
    clone = make_clone()
    sample = make_source("sample")
    mismatch_files = {
        "dev-docs.yaml": MISMATCH_CONFIG,
        "schemas/files.schema.yaml": MISMATCH_SCHEMA,
        "files.yaml": "files:\n  - path: a.md\n",
        "a.md": "# A\n",
    }
    mismatch = make_source("mismatch", mismatch_files, git=False)
    served = serve(sample, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    before = served.settings.read_bytes()
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(path=mismatch.folder), cwd=mismatch.folder)
    # 検証
    assert served.settings.read_bytes() == before
    assert served.get("/_api/sources/sample/docs").status_code == 200
    assert "documents[0].schema" in run.text
    assert "records" in run.text


def _run_setup_for_registered(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    config: str,
) -> tuple[Any, Any, Any, Any]:
    """`dev-docs.yaml` を `config` にした登録済みの配信元で `/dev-docs:setup` を動かし、必要な値を返す。"""
    clone = make_clone()
    files = {**_registered_files(), "dev-docs.yaml": config}
    notes = make_source("notes", files, git=False)
    notes.scope_write = [notes.folder]
    served = serve(notes, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    run = claude_home.run(SETUP_PROMPT.format(path=notes.folder), cwd=notes.folder)
    return clone, notes, served, run


def test_normal_when_schema_line_outdated(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
) -> None:
    """`dev-docs.yaml` の 1 行目のスキーマの行のタグが古いと、クローンのバージョンに書き換える（正常系）。"""
    # 準備・実行
    outdated = SCHEMA_LINE.format(version="0.0.1") + NOTES_CONFIG
    clone, notes, served, run = _run_setup_for_registered(
        claude_home, make_clone, make_source, serve, outdated
    )
    # 検証
    lines = (notes.folder / "dev-docs.yaml").read_text(encoding="utf-8").splitlines(keepends=True)
    checked = served.call_admin("check_project", path=str(notes.folder), format="json")
    assert not run.result["is_error"]
    assert lines[0] == SCHEMA_LINE.format(version=clone.version)
    assert "".join(lines[1:]) == NOTES_CONFIG
    assert checked.data.get("violations", []) == []


def test_normal_when_schema_line_missing(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
) -> None:
    """`dev-docs.yaml` の 1 行目にスキーマの行が無いと、クローンのバージョンのタグで入れる（正常系）。"""
    # 準備・実行
    clone, notes, served, run = _run_setup_for_registered(
        claude_home, make_clone, make_source, serve, NOTES_CONFIG
    )
    # 検証
    text = (notes.folder / "dev-docs.yaml").read_text(encoding="utf-8")
    checked = served.call_admin("check_project", path=str(notes.folder), format="json")
    assert not run.result["is_error"]
    assert text == SCHEMA_LINE.format(version=clone.version) + NOTES_CONFIG
    assert checked.data.get("violations", []) == []


def test_normal_when_source_config_unmigratable(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """`dev-docs migrate --source` が止まった移せない設定を、管理用の YAML の行へ移す（正常系）。"""
    # 準備
    clone = make_clone()
    markdown = {
        "docs/a.md": "---\nname: 文書 A\n---\n# A\n\nA の本文。\n",
        "docs/b.md": "---\nname: 文書 B\n---\n# B\n\nB の本文。\n",
    }
    notes = make_source(
        "notes",
        {
            "dev-docs.yaml": UNMIGRATABLE_CONFIG,
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            **markdown,
        },
        git=False,
    )
    notes.scope_write = [notes.folder]
    served = serve(notes, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    migrated = clone.migrate(served.settings, "--source", str(notes.folder / "dev-docs.yaml"))
    # 実行
    run = claude_home.run(SETUP_PROMPT.format(path=notes.folder), cwd=notes.folder)
    # 検証
    config_text = (notes.folder / "dev-docs.yaml").read_text(encoding="utf-8")
    config = load_yaml_file(notes.folder / "dev-docs.yaml")
    rows = {
        row["path"]: row for row in load_yaml_file(next(notes.folder.rglob("files.yaml")))["files"]
    }
    checked = served.call_admin("check_project", path=str(notes.folder), format="json")
    reloaded = served.call_admin("reload")
    found = served.call("search_docs", cwd=str(notes.folder), view="summary", format="json")
    assert migrated.returncode != 0
    assert not run.result["is_error"]
    assert sorted(Path(path).name for path in rows) == ["a.md", "b.md"]
    assert {Path(path).name: row["name"] for path, row in rows.items()} == {
        "a.md": "文書 A",
        "b.md": "文書 B",
    }
    assert all(row["tags"] == ["doc"] for row in rows.values())
    assert "type" not in config["documents"][0]
    assert "defaults" not in config["documents"][0]
    assert config["documents"][0]["records"] == "files"
    assert config["documents"][0]["body_file"] == "path"
    assert config["version"] == "3"
    assert config_text.startswith(SCHEMA_LINE.format(version=clone.version))
    for name, text in markdown.items():
        assert (notes.folder / name).read_text(encoding="utf-8") == text.split("---\n", 2)[2]
    assert checked.data.get("violations", []) == []
    assert not reloaded.is_error
    assert sorted(item["values"]["name"] for item in found.data["items"]) == ["文書 A", "文書 B"]


def test_normal_when_excluded_and_related_candidates(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    add_worktree: Callable[..., Path],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """除外の条件に当たるファイルの行を作らず、`implements`・`tests` の候補を付ける（正常系）。"""
    # 準備
    clone = make_clone()
    sample = make_source(
        "sample",
        {
            "dev-docs.yaml": CANDIDATES_CONFIG,
            "schemas/design.schema.yaml": DESIGN_SCHEMA,
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            "design/repo.yaml": (
                "id: design/repo\nname: タスクのリポジトリ\nimplementation: src/tasks/repo.py\n"
            ),
            "src/files.yaml": "files: []\n",
            "src/tasks/repo.py": "repo = 1\n",
            "src/tasks/test_repo.py": "test_repo = 1\n",
            "src/tasks/__init__.py": "",
            "src/uv.lock": "version = 1\n",
            "src/logo.png": "\x00PNG\n",
        },
    )
    sample.scope_write = [sample.folder]
    served = serve(sample, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    # Git の配信元のクローン本体には書けないため、ワークツリーで path を省いて実行する
    worktree = add_worktree(sample.folder, "x")
    # 実行
    run = claude_home.run(
        "/dev-docs:setup",
        cwd=worktree,
        answers=[(IMPLEMENTATION_QUESTION, IMPLEMENTATION_ANSWER)],
    )
    # 検証
    rows = _rows(load_yaml_file, worktree / "src")
    related = {
        path: [(item["to"], item["type"]) for item in row.get("related", [])]
        for path, row in rows.items()
    }
    shown = "\n".join([*run.question_texts, run.text])
    checked = served.call_admin("check_project", path=str(worktree), format="json")
    traced = served.call(
        "trace_related",
        cwd=str(worktree),
        from_ids=["design/repo"],
        direction="in",
        depth=1,
        format="json",
    )
    assert not run.result["is_error"]
    assert sorted(rows) == ["tasks/repo.py", "tasks/test_repo.py"]
    assert related["tasks/repo.py"] == [("design/repo", "implements")]
    assert related["tasks/test_repo.py"] == [("src/tasks/repo", "tests")]
    assert "implements" in shown
    assert "tests" in shown
    assert checked.data.get("violations", []) == []
    assert checked.data["sync"] == SYNC_ZERO
    assert [item["id"] for item in traced.data["items"]] == ["src/tasks/repo"]


def _settings_rows(settings: Any) -> dict[str, Any]:
    """端末の設定の `sources` を、配信元の ID から行を引く辞書にする。"""
    return {row["id"]: row for row in settings["sources"]}


def _source_row(page: Page, source_id: str) -> Locator:
    """設定画面の配信元の一覧から、`source_id` の行のロケータを返す。"""
    return page.get_by_role("row").filter(has=page.get_by_role("cell", name=source_id, exact=True))


def _add_source(page: Page, source_id: str, config: Path, read: str) -> None:
    """設定画面の追加のダイアログに入力して追加を押す。"""
    dialog = page.get_by_role("dialog")
    page.get_by_role("button", name="配信元を追加").click()
    dialog.get_by_label("配信元の ID").fill(source_id)
    dialog.get_by_label("設定ファイル").fill(str(config))
    dialog.get_by_label("読み取りの範囲").fill(read)
    dialog.get_by_role("button", name="追加", exact=True).click()


def test_normal_when_added_from_settings(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
    page: Page,
) -> None:
    """設定画面から配信元を追加し、再起動せずに配信する（正常系）。"""
    # 準備
    sample = make_source("sample")
    extra = make_source("extra")
    served = serve(sample)
    sample_row = _settings_rows(load_yaml_file(served.settings))["sample"]
    page.goto(served.url("/_settings"))
    # 実行
    _add_source(page, "extra", extra.folder / "dev-docs.yaml", f"{extra.folder}/**")
    # 検証
    expect(_source_row(page, "extra")).to_contain_text("配信中")
    expect(_source_row(page, "sample")).to_contain_text("配信中")
    rows = _settings_rows(load_yaml_file(served.settings))
    assert list(rows) == ["sample", "extra"]
    assert rows["sample"] == sample_row
    page.goto(served.url("/extra"))
    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_have_text("文書 1")


def test_normal_when_source_not_served(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    page: Page,
) -> None:
    """設定画面が、配信していない・設定が古い・無効の配信元を状態と理由つきで出す（正常系）。"""
    # 準備
    sample = make_source("sample")
    legacy_config = sample_config_text(name="legacy", version="0")
    legacy = make_source("legacy", sample_file_set(**{"dev-docs.yaml": legacy_config}))
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, git=False)
    archive = make_source("archive", enabled=False)
    served = serve(sample, legacy, broken, archive)
    # 実行
    page.goto(served.url("/_settings"))
    # 検証
    expect(_source_row(page, "sample")).to_contain_text("配信中")
    expect(_source_row(page, "legacy")).to_contain_text("配信中")
    expect(_source_row(page, "legacy")).to_contain_text("設定のバージョン 0（サーバーが読めるのは")
    expect(_source_row(page, "broken")).to_contain_text("配信していない")
    expect(_source_row(page, "broken")).to_contain_text("documents[0].paths")
    expect(_source_row(page, "archive")).to_contain_text("無効")
    expect(_source_row(page, "archive")).to_contain_text("enabled が false です")


def test_normal_when_added_source_invalid(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
    page: Page,
) -> None:
    """設定画面で追加した配信元が検証に通らないと、端末の設定には残し、配信から外す（正常系）。"""
    # 準備
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, git=False)
    served = serve(make_source("sample"))
    page.goto(served.url("/_settings"))
    # 実行
    _add_source(page, "broken", broken.folder / "dev-docs.yaml", f"{broken.folder}/**")
    # 検証
    expect(_source_row(page, "broken")).to_contain_text("配信していない")
    expect(_source_row(page, "broken")).to_contain_text("documents[0].paths")
    assert list(_settings_rows(load_yaml_file(served.settings))) == ["sample", "broken"]
    page.goto(served.url("/broken/docs/doc-1"))
    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_have_text(
        "配信元 broken を配信していません"
    )
    page.goto(served.url("/sample"))
    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_have_text("文書 1")


def test_error_when_schema_invalid(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    page: Page,
) -> None:
    """設定画面の保存が検証に通らないと、違反を項目ごとに出し、端末の設定を書き換えない（異常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    before = served.settings.read_bytes()
    page.goto(served.url("/_settings"))
    dialog = page.get_by_role("dialog")
    # 実行
    _add_source(page, "Sample Docs", sample.folder / "dev-docs.yaml", "/a/**\n\n/b/**")
    # 検証
    expect(dialog.get_by_role("alert")).to_contain_text("保存できませんでした")
    expect(dialog).to_contain_text("配信元の ID に使えない文字があります")
    expect(dialog).to_contain_text("読み取りの範囲に空の行があります")
    expect(dialog.get_by_label("配信元の ID")).to_have_value("Sample Docs")
    assert served.settings.read_bytes() == before
    page.goto(served.url("/sample"))
    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_have_text("文書 1")


def test_error_when_cross_origin(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    free_port: Callable[[], int],
) -> None:
    """画面と別のオリジンからの端末の設定の保存は 403 で断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    before = served.settings.read_bytes()
    payload = {
        "sources": [
            {
                "id": "sample",
                "config": [str(sample.folder / "dev-docs.yaml")],
                "scope": {"read": [str(sample.folder)]},
            }
        ]
    }
    # 実行
    response = httpx.put(
        served.url("/_api/settings/sources"),
        json=payload,
        headers={"Origin": f"http://127.0.0.1:{free_port()}"},
        timeout=10,
    )
    # 検証
    assert response.status_code == 403
    assert served.settings.read_bytes() == before
    assert served.get("/_api/sources/sample/docs").status_code == 200


def _repository_with_develop(
    make_source: Callable[..., Any], run_git: Callable[..., str]
) -> tuple[Any, Path]:
    """クローン本体が master で、`.claude/worktrees/develop` に develop を checkout した配信元を作る。"""
    repo = make_source("repo")
    run_git(repo.folder, "checkout", "-b", "master")
    develop = repo.folder / ".claude" / "worktrees" / "develop"
    run_git(repo.folder, "worktree", "add", str(develop), "develop")
    return repo, develop


def _worktree_paths(described: Any) -> set[str]:
    """describe(source) の JSON のワークツリーのパスを集める。"""
    return {item["path"] for item in described.data["worktrees"]}


def test_normal_when_main_repository_registered(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    write_settings: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """メインのリポジトリの dev-docs.yaml を指して追加すると、ワークツリーを数えて配信する（正常系）。"""
    # 準備
    sample = make_source("sample")
    repo, develop = _repository_with_develop(make_source, run_git)
    served = serve(sample)
    settings = write_settings(sample, repo)
    # 実行
    reloaded = served.call_admin("reload")
    described = served.call("describe", cwd=str(repo.folder), source="repo", format="json")
    outside = served.call(
        "search_docs", cwd=str(sample.folder), source="repo", outside_scope=True, view="ids"
    )
    settings.write_text(
        settings.read_text(encoding="utf-8").replace(
            "  - id: repo\n", '  - id: repo\n    outside_read: "yes"\n'
        ),
        encoding="utf-8",
    )
    invalid = served.call_admin("reload")
    # 検証
    assert not reloaded.is_error
    assert str(develop) in _worktree_paths(described)
    assert not outside.is_error
    assert invalid.is_error
    assert "outside_read" in invalid.text


def test_normal_when_worktree_config_registered(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    write_settings: Callable[..., Path],
    run_git: Callable[..., str],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """ワークツリーの dev-docs.yaml を指して追加しても、メインのリポジトリの直下からワークツリーを数える（正常系）。"""
    # 準備
    sample = make_source("sample")
    repo, develop = _repository_with_develop(make_source, run_git)
    worktree = add_worktree(repo.folder, "x")
    (worktree / "docs" / "doc-1.yaml").write_text(
        sample_doc_text("doc-1", "ワークツリー x の文書 1"), encoding="utf-8"
    )
    repo.config = [develop / "dev-docs.yaml"]
    served = serve(sample)
    write_settings(sample, repo)
    # 実行
    reloaded = served.call_admin("reload")
    described = served.call("describe", cwd=str(repo.folder), source="repo", format="json")
    found = served.call(
        "search_docs",
        cwd=str(worktree),
        worktree=str(worktree),
        filter={"field": "id", "op": "eq", "values": ["doc-1"]},
        view="full",
    )
    # 検証
    assert not reloaded.is_error
    assert str(worktree) in _worktree_paths(described)
    assert str(develop) in _worktree_paths(described)
    assert "name: ワークツリー x の文書 1" in found.text
