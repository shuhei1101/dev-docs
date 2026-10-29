from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

TEMPLATES = Path(__file__).parents[3] / "templates"
FILES_SCHEMA = TEMPLATES / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
SYNC_ZERO = {"missing_refs": 0, "unindexed_files": 0, "missing_body_files": 0}
TOOL_COUNT = 6
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
SCHEMA_LINE = (
    "# yaml-language-server: $schema="
    "https://raw.githubusercontent.com/shuhei1101/dev-docs/v{version}/schemas/dev-docs.schema.json\n"
)
NOTES_CONFIG = """\
version: "2"
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
    notes = make_source("notes", dict(MARKDOWN_FILES))
    # `.git`・`node_modules`・`.claude/worktrees` の下のファイルは範囲に入れない
    for ignored in ("node_modules/pkg/README.md", ".claude/worktrees/x/memo.md"):
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
    assert schema_errors(FILES_SCHEMA, loaded) == []
    assert len(found.data["items"]) == len(MARKDOWN_FILES)


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
    assert config["version"] == "2"
    assert config_text.startswith(SCHEMA_LINE.format(version=clone.version))
    for name, text in markdown.items():
        assert (notes.folder / name).read_text(encoding="utf-8") == text.split("---\n", 2)[2]
    assert checked.data.get("violations", []) == []
    assert not reloaded.is_error
    assert sorted(item["values"]["name"] for item in found.data["items"]) == ["文書 A", "文書 B"]
