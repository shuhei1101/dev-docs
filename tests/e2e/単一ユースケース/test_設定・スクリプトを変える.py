from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

BROKEN_CONFIG = "name: sample\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
CONVERT_OK = "import sys\nsys.stdin.read()\nprint('# 変換した')\n"
CONVERT_FAILING = "import sys\nprint('変換に失敗した', file=sys.stderr)\nsys.exit(3)\n"
CONVERTER_EXTRA = (
    "    converter: md\nconverters:\n  - id: md\n    run: [python3, scripts/convert.py]\n"
)
MCP_TAB = {
    "title": "mcp",
    "items": [{"auto": {"filter": {"field": "tags", "op": "eq", "values": ["mcp"]}}}],
}
DESIGN_ITEMS = {
    "items": [{"auto": {"filter": {"field": "tags", "op": "eq", "values": ["設計"]}}}],
}
BAD_TAB = {
    "title": "bad",
    "items": [{"auto": {"filter": {"field": "tags", "op": "like", "values": ["mcp"]}}}],
}
NONE_TAB = {
    "title": "none",
    "items": [{"auto": {"filter": {"field": "tags", "op": "eq", "values": ["none"]}}}],
}
FIRST_TAB = "nav.tabs[0].items[0].auto"
NONE_TAB_PATH = "nav.tabs[1].items[0].auto"
TERM_ROW = (
    "  - id: terms\n"
    "    paths: [terms/*.yaml]\n"
    "    schema: schemas/term.schema.yaml\n"
    "    alias_type: term\n"
)
TERM_SCHEMA = "title: 用語\ntype: object\n"
BROKEN_TERM = "id: broken\nname: 壊れた用語\ndescription: 型の違う別名\naliases: 3\n"
NONE_NAV = (
    "nav:\n"
    "  tabs:\n"
    "    - title: none\n"
    "      items:\n"
    "        - auto: {filter: {field: tags, op: eq, values: [none]}}\n"
)
ALIAS_SCHEMA_VERSION = "v0.3.0"
SCRIPTS_ROW = (
    "  - id: converted\n"
    "    paths: [converted/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    converter: md\n"
    "    validators: [check]\n"
    "converters:\n"
    "  - id: md\n"
    "    run: [python3, scripts/convert.py]\n"
    "validators:\n"
    "  - id: check\n"
    "    run: [python3, scripts/check.py]\n"
    "    on: [read]\n"
)
CONVERTED_DOC = "id: c-1\nname: 変換する文書\n"
DEVELOP_CONVERT = (
    "import sys\ntext = sys.stdin.read()\nprint('develop の変換')\nprint()\nprint('# 変換した')\n"
)
MASTER_CONVERT = "import sys\nsys.stdin.read()\nprint('# 変換した')\n"
WORKTREE_CONVERT = (
    "import sys\nsys.stdin.read()\nprint('worktree-x の変換')\nprint()\nprint('# 変換した')\n"
)
DEVELOP_CHECK = "import json\nprint(json.dumps([{'path': 'name', 'rule': 'develop-rule'}]))\n"
MASTER_CHECK = "import json\nprint(json.dumps([]))\n"
C_1 = {"field": "id", "op": "eq", "values": ["c-1"]}
SYNC_ZERO = {"missing_refs": 0, "unindexed_files": 0, "missing_body_files": 0}


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_config_text: Callable[..., str],
    snapshot: Callable[..., dict[str, bytes]],
) -> None:
    """設定を変えて `check_project`・`try_convert` で確かめ、`reload` で配信に入れる（正常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    pid = served.call_admin("status", format="json").data["pid"]
    (sample.folder / "dev-docs.yaml").write_text(
        sample_config_text(description="書き換えた説明"), encoding="utf-8"
    )
    before = snapshot(sample.folder)
    # 実行
    checked = served.call_admin("check_project", path=str(sample.folder), format="json")
    converted = served.call_admin("try_convert", path=str(sample.folder), file="docs/doc-1.yaml")
    unchanged = snapshot(sample.folder) == before
    described_before = served.call("describe", cwd=str(sample.folder))
    reloaded = served.call_admin("reload", format="json")
    described_after = served.call("describe", cwd=str(sample.folder))
    status = served.call_admin("status", format="json").data
    # 検証
    assert not checked.is_error
    assert checked.data.get("violations", []) == []
    assert checked.data["sync"] == SYNC_ZERO
    assert not converted.is_error
    assert "文書 1" in converted.data["markdown"]
    assert unchanged
    assert "書き換えた説明" not in described_before.text
    assert not reloaded.is_error
    assert "書き換えた説明" in described_after.text
    assert not described_before.is_error
    assert status["pid"] == pid


def test_normal_when_config_version_old(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """設定のバージョンが古い配信元は、古い設定として返す（正常系）。"""
    # 準備
    config = sample_config_text(name="old", version="0")
    old = make_source("old", sample_file_set(**{"dev-docs.yaml": config}))
    served = serve(old)
    # 実行
    checked = served.call_admin("check_project", path=str(old.folder), format="json")
    # 検証
    assert not checked.is_error
    assert checked.data["config_version"] == "0"
    assert checked.data["version_state"] == "old"
    assert checked.data.get("violations", []) == []


def test_error_when_config_invalid(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """変えた設定が検証に通らないと違反を返し、`reload` までは変える前の設定で配信する（異常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    (sample.folder / "dev-docs.yaml").write_text(BROKEN_CONFIG, encoding="utf-8")
    # 実行
    checked = served.call_admin("check_project", path=str(sample.folder), format="json")
    searched = served.call(
        "search_docs", cwd=str(sample.folder), source="sample", view="ids", format="json"
    )
    # 検証
    violations = checked.data["violations"]
    assert [item["path"] for item in violations] == ["documents[0].paths"]
    assert violations[0]["rule"]
    assert not searched.is_error
    assert [item["id"] for item in searched.data["items"]] == ["doc-1", "doc-2"]


def test_error_when_converter_fails(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    snapshot: Callable[..., dict[str, bytes]],
) -> None:
    """変換スクリプトが失敗すると、終了コードと標準エラーを返し、配信は変えない（異常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(CONVERTER_EXTRA),
            "scripts/convert.py": CONVERT_OK,
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    (sample.folder / "scripts" / "convert.py").write_text(CONVERT_FAILING, encoding="utf-8")
    before = snapshot(sample.folder)
    # 実行
    converted = served.call_admin("try_convert", path=str(sample.folder), file="docs/doc-1.yaml")
    status = served.call_admin("status", format="json").data
    # 検証
    assert converted.is_error
    assert "3" in converted.text
    assert "変換に失敗した" in converted.text
    assert snapshot(sample.folder) == before
    assert [source["id"] for source in status["sources"] if source["status"] == "serving"] == [
        "sample"
    ]


def _counts(result: Any) -> dict[str, int]:
    """`counts` を auto のキーのパスと文書の数の対応にする。"""
    return {item["path"]: item["count"] for item in result.data["counts"]}


def _without_nav(value: dict[str, Any]) -> dict[str, Any]:
    """設定の YAML の値から `nav` を除く。"""
    return {key: item for key, item in value.items() if key != "nav"}


def _scripts_source(
    make_source: Callable[..., Any],
    run_git: Callable[..., str],
    commit_all: Callable[..., str],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> Any:
    """develop に develop のスクリプトを持ち、クローン本体が master のスクリプトで master を踏む sample を作る。"""
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(SCRIPTS_ROW),
            "converted/c-1.yaml": CONVERTED_DOC,
            "scripts/convert.py": DEVELOP_CONVERT,
            "scripts/check.py": DEVELOP_CHECK,
        }
    )
    sample = make_source("sample", files)
    run_git(sample.folder, "checkout", "-b", "master")
    commit_all(
        sample.folder,
        {"scripts/convert.py": MASTER_CONVERT, "scripts/check.py": MASTER_CHECK},
        "scripts: master のスクリプト",
    )
    return sample


def test_normal_when_nav_written_by_admin_mcp(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
    load_yaml_file: Callable[[Path], Any],
) -> None:
    """管理の MCP の write_nav で、ワークツリーの dev-docs.yaml の nav を検証してから書く（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "docs/doc-1.yaml": sample_doc_text("doc-1", "文書 1", tags=["mcp"]),
            "docs/doc-2.yaml": sample_doc_text("doc-2", "文書 2", tags=["設計"]),
            "docs/doc-3.yaml": sample_doc_text("doc-3", "文書 3", tags=["mcp", "設計"]),
        }
    )
    sample = make_source("sample", files)
    worktree = add_worktree(sample.folder, "x")
    config = worktree / "dev-docs.yaml"
    before = load_yaml_file(config)
    served = serve(sample)
    path = str(worktree)
    # 実行
    added = served.call_admin(
        "write_nav",
        path=path,
        operations=[{"op": "add", "tab": "mcp", "value": MCP_TAB}],
        format="json",
    )
    after_add = load_yaml_file(config)
    updated = served.call_admin(
        "write_nav",
        path=path,
        operations=[{"op": "update", "tab": "mcp", "value": DESIGN_ITEMS}],
        format="json",
    )
    after_update = load_yaml_file(config)
    bad = served.call_admin(
        "write_nav", path=path, operations=[{"op": "add", "tab": "bad", "value": BAD_TAB}]
    )
    after_bad = load_yaml_file(config)
    none = served.call_admin(
        "write_nav",
        path=path,
        operations=[{"op": "add", "tab": "none", "value": NONE_TAB}],
        format="json",
    )
    after_none = load_yaml_file(config)
    # 検証
    assert not added.is_error
    assert after_add["nav"]["tabs"] == [MCP_TAB]
    assert _counts(added)[FIRST_TAB] == 2
    assert not updated.is_error
    assert after_update["nav"]["tabs"] == [{"title": "mcp", **DESIGN_ITEMS}]
    assert _counts(updated)[FIRST_TAB] == 2
    assert bad.is_error
    assert after_bad == after_update
    assert not none.is_error
    assert [tab["title"] for tab in after_none["nav"]["tabs"]] == ["mcp", "none"]
    assert _counts(none)[NONE_TAB_PATH] == 0
    assert len(none.data["warnings"]) == 1
    assert _without_nav(after_none) == _without_nav(before)


def test_normal_when_check_project_reports_alias_and_nav(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_config_text: Callable[..., str],
) -> None:
    """check_project が、エイリアスのキーの違反と 0 件に当たる nav の条件を返す（正常系）。"""
    # 準備
    sample = make_source("sample")
    worktree = add_worktree(sample.folder, "x")
    (worktree / "dev-docs.yaml").write_text(
        sample_config_text(TERM_ROW + NONE_NAV), encoding="utf-8"
    )
    (worktree / "schemas" / "term.schema.yaml").write_text(TERM_SCHEMA, encoding="utf-8")
    (worktree / "terms").mkdir()
    (worktree / "terms" / "broken.yaml").write_text(BROKEN_TERM, encoding="utf-8")
    served = serve(sample)
    # 実行
    result = served.call_admin("check_project", path=str(worktree), format="json")
    # 検証
    alias_violations = [item for item in result.data["violations"] if item["path"] == "aliases"]
    assert not result.is_error
    assert len(alias_violations) == 1
    assert alias_violations[0]["doc"] == "terms/broken.yaml"
    assert len(result.data["warnings"]) == 1
    assert "none" in result.data["warnings"][0]["rule"]
    assert result.data["alias_schema_version"] == ALIAS_SCHEMA_VERSION


def test_normal_when_scripts_run_from_default_ref(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    run_git: Callable[..., str],
    commit_all: Callable[..., str],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """クローン本体が master でも、検査と変換のスクリプトを default_ref の develop から動かす（正常系）。"""
    # 準備
    sample = _scripts_source(make_source, run_git, commit_all, sample_file_set, sample_config_text)
    served = serve(sample)
    # 実行
    searched = served.call(
        "search_docs", cwd=str(sample.folder), filter=C_1, view="summary", format="json"
    )
    document = served.get("/_api/sources/sample/docs/converted/c-1")
    # 検証
    assert any("develop-rule" in note for note in searched.data["notes"])
    assert document.json()["markdown"].startswith("develop の変換")


def test_normal_when_scripts_run_from_worktree(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
    commit_all: Callable[..., str],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """ワークツリーを指すと、ワークツリーの commit していない変換スクリプトで変換する（正常系）。"""
    # 準備
    sample = _scripts_source(make_source, run_git, commit_all, sample_file_set, sample_config_text)
    worktree = add_worktree(sample.folder, "x")
    (worktree / "scripts" / "convert.py").write_text(WORKTREE_CONVERT, encoding="utf-8")
    served = serve(sample)
    # 実行
    in_worktree = served.call_admin("try_convert", path=str(worktree), file="converted/c-1.yaml")
    in_clone = served.get("/_api/sources/sample/docs/converted/c-1")
    # 検証
    assert not in_worktree.is_error
    assert in_worktree.data["markdown"].startswith("worktree-x の変換")
    assert "develop の変換" not in in_worktree.data["markdown"]
    assert in_clone.json()["markdown"].startswith("develop の変換")
