from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

FILES_SCHEMA = Path(__file__).parents[3] / "templates" / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
FILES_REQUIRED = "'files' is a required property"
SEEN = "（この会話で返し済み）"
NOTES_ROWS = (
    "  - id: notes\n"
    "    paths: [notes/**/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)
DECISIONS_ROW = (
    "  - id: decisions\n"
    "    paths: [decisions/*.yaml]\n"
    "    schema: schemas/decision.schema.yaml\n"
    "    metadata: {name: title, description: meta.summary}\n"
)
DECISION_SCHEMA = (
    "type: object\n"
    "properties:\n"
    "  id: {type: string}\n"
    "  title: {type: string}\n"
    "  meta:\n"
    "    type: object\n"
    "    properties:\n"
    "      summary: {type: string}\n"
)
DESIGN_AND_SRC_ROWS = (
    "  - id: design\n"
    "    paths: [design/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "  - id: src\n"
    "    paths: [src/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)
SRC_FILES = (
    "files:\n"
    "  - path: repo.py\n"
    "    related:\n"
    "      - {to: design/repo, type: implements}\n"
    "  - path: test_repo.py\n"
    "    related:\n"
    "      - {to: src/repo.py, type: tests}\n"
)
SEARCH_WORD = {"field": "body", "op": "contains", "values": ["検索"]}
IN_ARCHIVE = {"field": "@path", "op": "glob", "values": ["notes/archive/**"]}
BY_MATCHES = {"fields": ["@matches"], "order_by": [{"field": "@matches", "direction": "desc"}]}
NOTES_A = {"field": "id", "op": "eq", "values": ["notes/a.md"]}
OUTSIDE_LINE = "作業範囲の外（参考）"
OUTSIDE_LOG = "作業範囲の外を読んだ"
OUTSIDE_HINT = "outside_scope: true"
OBJECT_TAGS_ROW = (
    "  - id: rules\n"
    "    paths: [rules/*.yaml]\n"
    "    schema: schemas/rule.schema.yaml\n"
    '    metadata: {tags: "tags[].name", main_tags: "tags[main].name"}\n'
)
OBJECT_TAGS_SCHEMA = (
    "type: object\n"
    "properties:\n"
    "  id: {type: string}\n"
    "  name: {type: string}\n"
    "  tags:\n"
    "    type: array\n"
    "    items:\n"
    "      type: object\n"
    "      properties:\n"
    "        name: {type: string}\n"
    "        main: {type: boolean}\n"
)
TAG_MCP = {"field": "tags", "op": "eq", "values": ["mcp"]}
MAIN_TAG_MCP = {"field": "main_tags", "op": "eq", "values": ["mcp"]}
IN_RULES = {"field": "kind", "op": "eq", "values": ["rules"]}
TERM_ROW = (
    "  - id: terms\n"
    "    paths: [terms/*.yaml]\n"
    "    schema: schemas/term.schema.yaml\n"
    "    alias_type: term\n"
)
TERM_SCHEMA = "title: 用語\ntype: object\n"
SCOPE_TERM = "id: scope\nname: 作業範囲\ndescription: 触ってよい範囲\naliases: [scope, 担当範囲]\n"
SESSION_CONTEXT = "/_admin/session-context"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "e2e-test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
CONTEXT_MAX_CHARS = 1000
TAG_HEADER = "タグ:"
TAG_RULES = (
    "複合語は単語まで分けてタグにする",
    "`action:`",
    "`topic:`",
    "`tool:`",
    "配信元にタグの規約があれば",
    '`group_by="tags"` で使われているタグを見て',
)
# 使い分けは文書の MCP の instructions にある旨の行
POINTER_LINE = (
    "探す・読む・書くときの使い分けと書き方は、文書の MCP（dev-docs）の instructions にあります。"
)
INSTRUCTIONS_MAX_CHARS = 4096
# instructions が案内する、使う場面・grep と Read が向く場面・ツールの順序の語
INSTRUCTIONS_GUIDES = (
    "使う場面:",
    "`search_docs`",
    "`trace_related`",
    "`list_changes`",
    "`write_docs`",
    "grep・Read が向く場面:",
    "コードの識別子・文字列の出現箇所",
    "配信の範囲の外のファイル",
    "始めに `describe(source)` で種類と書き方を確かめる",
)
# description が持つ、いつ使う・何を返さないの語
DESCRIPTION_GUIDES = ("ときに使う", "返さない")
FORBIDDEN_WORDS = ("MUST", "必ず", "禁止")
TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
PART_LINES = [
    "# a",
    "2 行目 検索",
    "## 経緯",
    "経緯の本文",
    "",
    "## 決まったこと",
    "7 行目 検索",
    "詳細",
    "## 残り",
    "残りの本文",
]


def _notes_files(
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    notes: dict[str, str],
) -> dict[str, str]:
    """管理用の YAML で Markdown を配信する行 `notes` と、notes の文書を持つ配信元のファイル一式を返す。

    管理用の YAML はフォルダごとに `files.yaml` を置き、そのフォルダの Markdown を 1 行ずつ載せる。
    """
    indexes: dict[str, list[str]] = {}
    for name in notes:
        folder, _, base = name.rpartition("/")
        indexes.setdefault(folder, []).append(f"  - path: {base}\n")
    index_files = {
        f"{folder}/files.yaml": "files:\n" + "".join(rows) for folder, rows in indexes.items()
    }
    return sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(NOTES_ROWS),
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            **index_files,
            **notes,
        }
    )


def _related_files(
    sample_file_set: Callable[..., dict[str, str]], sample_doc_text: Callable[..., str]
) -> dict[str, str]:
    """文書 1 の related が文書 2 を指す、配信元のファイル一式を返す。"""
    return sample_file_set(
        **{
            "docs/doc-1.yaml": sample_doc_text(
                "doc-1",
                "文書 1",
                description="1 件目",
                related=[{"to": "doc-2", "type": "references"}],
            )
        }
    )


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """使える配信元・種類・文書を順に絞って読む（正常系）。"""
    # 準備
    sample = make_source("sample", _related_files(sample_file_set, sample_doc_text))
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    arguments = {"cwd": str(sample.folder)}
    # 実行
    sources = served.call("describe", **arguments)
    detail = served.call("describe", source="sample", **arguments)
    summary = served.call(
        "search_docs",
        filter={"field": "kind", "op": "eq", "values": ["sample"]},
        view="summary",
        **arguments,
    )
    full = served.call("search_docs", filter=DOC_1, view="full", **arguments)
    related = served.call("trace_related", from_ids=["doc-1"], format="json", **arguments)
    # 検証
    rows = [line for line in summary.text.splitlines() if line.startswith("| doc-")]
    assert "| sample | write（作業中） |" in sources.text
    assert "| notes | read |" in sources.text
    assert "| sample |" in detail.text
    assert summary.text.startswith("sample: 該当 2 件・返した 2 件")
    assert [row.split("|")[1].strip() for row in rows] == ["doc-1", "doc-2"]
    assert all(re.search(r"\| [0-9a-f]{6} \|$", row) for row in rows)
    assert "id: doc-1" in full.text
    assert "name: 文書 1" in full.text
    assert f'<document path="{sample.folder}/docs/doc-1.yaml" scope="full">' in full.text
    assert [item["id"] for item in related.data["items"]] == ["doc-2"]


def test_normal_when_source_all(make_source: Callable[..., Any], serve: Callable[..., Any]) -> None:
    """scope.read に当たる全ての配信元を横断する（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    # 実行
    everything = served.call("search_docs", cwd=str(sample.folder), source="*", format="json")
    only_sample = served.call(
        "search_docs", cwd=str(sample.folder), source=["sample"], format="json"
    )
    # 検証
    assert {item["source"] for item in everything.data["items"]} == {"sample", "notes"}
    assert everything.data["per_source"] == {"sample": 2, "notes": 2}
    assert [item["id"] for item in only_sample.data["items"]] == ["doc-1", "doc-2"]
    assert "notes" not in only_sample.text


def test_normal_when_tags_grouped(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """表記だけが違うタグを 1 つにまとめて数え、そのタグで文書を絞る（正常系）。"""
    # 準備
    sample_files = sample_file_set(
        **{
            "docs/doc-1.yaml": sample_doc_text(
                "doc-1", "文書 1", description="1 件目", tags=["mcp"]
            ),
            "docs/doc-2.yaml": sample_doc_text(
                "doc-2", "文書 2", description="2 件目", tags=["MCP", "mcp", "設計"]
            ),
        }
    )
    notes_files = sample_file_set(
        **{
            "docs/doc-1.yaml": sample_doc_text(
                "doc-1", "メモ 1", description="1 件目", tags=["mcp"]
            ),
        }
    )
    del notes_files["docs/doc-2.yaml"]
    sample = make_source("sample", sample_files)
    notes = make_source("notes", notes_files, git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    arguments = {"cwd": str(sample.folder), "source": "*", "format": "json"}
    # 実行
    grouped = served.call("search_docs", view="count", group_by="tags", **arguments)
    tagged = served.call(
        "search_docs",
        filter={"field": "tags", "op": "eq", "values": ["mcp"]},
        view="summary",
        **arguments,
    )
    # 検証
    assert grouped.data["groups"] == [
        {"value": "mcp", "count": 3},
        {"value": "設計", "count": 1},
    ]
    assert tagged.data["total_count"] == 3
    assert sorted((item["source"], item["id"]) for item in tagged.data["items"]) == [
        ("notes", "doc-1"),
        ("sample", "doc-1"),
        ("sample", "doc-2"),
    ]


def test_normal_when_worktree_given(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """worktree か、ワークツリーの中の cwd で指したワークツリーの文書を読む（正常系）。"""
    # 準備
    sample = make_source("sample")
    worktree = add_worktree(sample.folder, "x")
    (worktree / "docs" / "doc-1.yaml").write_text(
        sample_doc_text("doc-1", "ワークツリーの名前"), encoding="utf-8"
    )
    served = serve(sample)
    arguments = {"filter": DOC_1, "view": "full"}
    # 実行
    by_worktree = served.call(
        "search_docs", cwd=str(sample.folder), worktree=str(worktree), **arguments
    )
    by_cwd = served.call("search_docs", cwd=str(worktree), **arguments)
    by_clone = served.call("search_docs", cwd=str(sample.folder), **arguments)
    # 検証
    assert "name: ワークツリーの名前" in by_worktree.text
    assert "name: ワークツリーの名前" in by_cwd.text
    assert "name: 文書 1" in by_clone.text
    assert "ワークツリーの名前" not in by_clone.text
    assert f'<document path="{worktree}/docs/doc-1.yaml" scope="full">' in by_worktree.text


def test_normal_when_same_doc_twice(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """同じ会話で同じバージョンの本文を 2 回目は省く（正常系）。"""
    # 準備
    sample = make_source("sample", _related_files(sample_file_set, sample_doc_text))
    served = serve(sample)
    full = {"cwd": str(sample.folder), "filter": DOC_1, "view": "full"}
    related = {"cwd": str(sample.folder), "from_ids": ["doc-1"], "format": "json"}
    summary = {"cwd": str(sample.folder), "view": "summary"}
    body = "id: doc-1\nname: 文書 1"
    # 実行
    first = served.call("search_docs", session_id="s1", **full)
    second = served.call("search_docs", session_id="s1", **full)
    repeated = served.call("search_docs", session_id="s1", repeat_seen=True, **full)
    other_session = served.call("search_docs", session_id="s2", **full)
    first_related = served.call("trace_related", session_id="s3", **related)
    second_related = served.call("trace_related", session_id="s3", **related)
    served.call("search_docs", session_id="s1", **summary)
    second_summary = served.call("search_docs", session_id="s1", **summary)
    # 検証
    assert body in first.text
    assert SEEN in second.text
    assert body not in second.text
    assert "<document>" in second.text
    assert "path=" not in second.text
    assert body in repeated.text
    assert body in other_session.text
    assert first_related.data["items"][0]["name"] == "文書 2"
    assert second_related.data["items"][0]["name"] == SEEN
    assert second_related.data["items"][0]["description"] == SEEN
    assert "1 件目" in second_summary.text


def test_normal_when_files_index(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """管理用の YAML で配信したソースコードを検索で引く（正常系）。"""
    # 準備
    src_row = (
        "  - id: src\n"
        "    paths: [src/files.yaml]\n"
        "    schema: schemas/files.schema.yaml\n"
        "    records: files\n"
        "    body_file: path\n"
    )
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(src_row),
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            "src/files.yaml": (
                "files:\n"
                "  - path: a.py\n"
                "    tags: [auth, code]\n"
                "  - path: b.py\n"
                "    name: 部品 B\n"
                "  - path: a.md\n"
            ),
            "src/a.py": "a = 1\n",
            "src/b.py": "b = 2\n",
            "src/a.md": "# A の説明\n",
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    by_id = {
        "cwd": str(sample.folder),
        "filter": {"field": "id", "op": "eq", "values": ["src/a.py"]},
    }
    # 実行
    tagged = served.call(
        "search_docs",
        cwd=str(sample.folder),
        filter={"field": "tags", "op": "eq", "values": ["auth"]},
        view="summary",
        fields=["tags"],
        format="json",
    )
    other = served.call(
        "search_docs",
        cwd=str(sample.folder),
        filter={"field": "id", "op": "eq", "values": ["src/b.py"]},
        view="summary",
        format="json",
    )
    markdown = served.call("search_docs", view="full", **by_id)
    as_json = served.call("search_docs", view="full", format="json", **by_id)
    same_stem = served.call(
        "search_docs",
        cwd=str(sample.folder),
        filter={"field": "id", "op": "eq", "values": ["src/a.md"]},
        view="full",
        format="json",
    )
    # 検証
    item = tagged.data["items"][0]
    located = as_json.data["items"][0]
    assert [row["id"] for row in tagged.data["items"]] == ["src/a.py"]
    assert item["values"]["name"] == "a"
    assert item["values"]["tags"] == ["auth", "code"]
    assert other.data["items"][0]["values"]["name"] == "部品 B"
    assert "a = 1" in markdown.text
    assert f'<document path="{sample.folder}/src/a.py" scope="full">' in markdown.text
    assert located["path"] == f"{sample.folder}/src/a.py"
    assert located["scope"] == "full"
    assert located["values"]["path"] == "a.py"
    assert [row["id"] for row in same_stem.data["items"]] == ["src/a.md"]
    assert same_stem.data["items"][0]["values"]["body"] == "# A の説明\n"
    assert same_stem.data["items"][0]["values"]["name"] == "a"
    assert not any(FILES_REQUIRED in note for note in tagged.data.get("notes", []))
    assert not any(FILES_REQUIRED in note for note in other.data.get("notes", []))
    assert not any(FILES_REQUIRED in note for note in as_json.data.get("notes", []))
    assert FILES_REQUIRED not in markdown.text


def test_error_when_source_not_readable(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """scope.read に当たらない配信元を指すと、使える配信元の一覧を返して文書は返さない（異常系）。"""
    # 準備
    sample = make_source("sample")
    other_files = sample_file_set(**{"docs/doc-1.yaml": "id: secret-1\nname: 秘密\n"})
    other = make_source("other", other_files)
    served = serve(sample, other)
    # 実行
    with_cwd = served.call("search_docs", cwd=str(sample.folder), source="other")
    without_cwd = served.call("search_docs", source="other")
    everything = served.call("search_docs", cwd=str(sample.folder), source="*", format="json")
    # 検証
    for result in (with_cwd, without_cwd):
        assert result.is_error
        assert "SourceNotReadableError" in result.text
        assert "other" in result.text
        assert "secret-1" not in result.text
    assert "sample" in with_cwd.text
    assert OUTSIDE_HINT in with_cwd.text
    assert [item["id"] for item in everything.data["items"]] == ["doc-1", "doc-2"]
    assert "other" not in everything.text
    assert "secret-1" not in everything.text


def test_error_when_source_not_served(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """起動時の検証で外した配信元を指すと、違反を返す（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, scope_read=[sample.folder])
    served = serve(sample, broken)
    # 実行
    result = served.call("search_docs", cwd=str(sample.folder), source="broken")
    other = served.call("search_docs", cwd=str(sample.folder), source="sample", format="json")
    # 検証
    assert result.is_error
    assert "SourceNotServedError" in result.text
    assert "broken" in result.text
    assert "documents[0].paths" in result.text
    assert [item["id"] for item in other.data["items"]] == ["doc-1", "doc-2"]


def test_error_when_worktree_not_matched(
    make_source: Callable[..., Any], serve: Callable[..., Any], tmp_path: Path
) -> None:
    """worktrees に当たらないパスを指すと、パスと worktrees の値を返す（異常系）。"""
    # 準備
    sample = make_source("sample")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    served = serve(sample)
    # 実行
    result = served.call("search_docs", cwd=str(sample.folder), worktree=str(elsewhere))
    # 検証
    assert result.is_error
    assert "WorktreeNotMatchedError" in result.text
    assert str(elsewhere) in result.text
    assert ".claude/worktrees" in result.text
    assert "doc-1" not in result.text


def test_normal_when_excluded_name(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """行の exclude に当たるファイルを外し、他の行に当たればその行の文書として返す（正常系）。"""
    # 準備
    rows = (
        "  - id: rule\n"
        "    paths: [docs/rule/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
        "    exclude: [index.yaml]\n"
        "  - id: index\n"
        "    paths: [docs/**/index.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
    )
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(rows),
            "docs/rule/a.yaml": "id: a\nname: a\n",
            "docs/rule/Rb.yaml": "id: Rb\nname: Rb\n",
            "docs/rule/index.yaml": "id: rule-index\nname: 目次\n",
        }
    )
    source = make_source("sample", files)
    served = serve(source)
    # 実行
    rule = served.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "kind", "op": "eq", "values": ["rule"]},
        view="summary",
        format="json",
    )
    index = served.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "kind", "op": "eq", "values": ["index"]},
        view="summary",
        format="json",
    )
    # 検証
    assert [item["id"] for item in rule.data["items"]] == ["a", "Rb"]
    assert [item["id"] for item in index.data["items"]] == ["rule-index"]


def test_normal_when_ordered_by_matches(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """当たった数で並べて絞る（正常系）。"""
    # 準備
    notes = {
        "notes/a.md": "検索 1\n検索 2\n検索 3\n他\n",
        "notes/b.md": "検索 1\n他\n",
        "notes/archive/c.md": "検索 1\n検索 2\n他\n",
    }
    files = _notes_files(sample_file_set, sample_config_text, notes)
    sample = make_source("sample", files)
    served = serve(sample)
    cwd = str(sample.folder)
    # 実行
    narrowed = served.call(
        "search_docs",
        cwd=cwd,
        filter={"and": [SEARCH_WORD, {"not": IN_ARCHIVE}]},
        format="json",
        **BY_MATCHES,
    )
    without_not = served.call(
        "search_docs", cwd=cwd, filter=SEARCH_WORD, format="json", **BY_MATCHES
    )
    # 検証
    assert [(item["id"], item["values"]["@matches"]) for item in narrowed.data["items"]] == [
        ("notes/a.md", 3),
        ("notes/b.md", 1),
    ]
    assert [(item["id"], item["values"]["@matches"]) for item in without_not.data["items"]] == [
        ("notes/a.md", 3),
        ("notes/archive/c.md", 2),
        ("notes/b.md", 1),
    ]


def test_normal_when_part_of_body(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """見つけた文書の本文の一部を読む（正常系）。"""
    # 準備
    text = "\n".join(PART_LINES) + "\n"
    files = _notes_files(sample_file_set, sample_config_text, {"notes/a.md": text})
    sample = make_source("sample", files)
    served = serve(sample)
    request = {"cwd": str(sample.folder), "filter": NOTES_A, "view": "full", "session_id": "s1"}
    # 実行
    by_section = served.call("search_docs", format="json", sections=["決まったこと"], **request)
    by_lines = served.call("search_docs", format="json", lines={"offset": 3, "limit": 2}, **request)
    whole = served.call("search_docs", format="json", **request)
    # 検証
    section_item = by_section.data["items"][0]
    assert section_item["values"]["body"] == "## 決まったこと\n7 行目 検索\n詳細"
    assert section_item["scope"] == "section"
    assert by_lines.data["items"][0]["values"]["body"] == "## 経緯\n経緯の本文"
    assert by_lines.data["items"][0]["scope"] == "section"
    assert whole.data["items"][0]["values"]["body"] == text
    assert whole.data["items"][0]["scope"] == "full"


def test_normal_when_metadata_mapped(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """列名の違う種類を共通のキーで引く（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(DECISIONS_ROW),
            "schemas/decision.schema.yaml": DECISION_SCHEMA,
            "decisions/d1.yaml": (
                "id: d1\ntitle: 設定の置き場所\nmeta:\n  summary: 設定を置く場所を決める\n"
            ),
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    cwd = str(sample.folder)
    # 実行
    described = served.call("describe", cwd=cwd, source="sample", kind="decisions", format="json")
    found = served.call(
        "search_docs",
        cwd=cwd,
        filter={"field": "name", "op": "eq", "values": ["設定の置き場所"]},
        view="summary",
        format="json",
    )
    # 検証
    assert described.data["metadata"] == {"name": "title", "description": "meta.summary"}
    assert [item["id"] for item in found.data["items"]] == ["d1"]
    assert found.data["items"][0]["values"]["name"] == "設定の置き場所"
    assert found.data["items"][0]["values"]["description"] == "設定を置く場所を決める"


def test_normal_when_implementing_code_traced(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    sample_doc_text: Callable[..., str],
) -> None:
    """設計書を起点に `direction: in` で、設計書を実装するコードを引く（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(DESIGN_AND_SRC_ROWS),
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            "design/repo.yaml": sample_doc_text("design/repo", "タスクのリポジトリ"),
            "src/files.yaml": SRC_FILES,
            "src/repo.py": "repo = 1\n",
            "src/test_repo.py": "test_repo = 1\n",
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    cwd = str(sample.folder)
    # 実行
    implementing = served.call(
        "trace_related", cwd=cwd, from_ids=["design/repo"], direction="in", depth=1, format="json"
    )
    testing = served.call(
        "trace_related", cwd=cwd, from_ids=["src/repo.py"], direction="in", depth=1, format="json"
    )
    bodies = served.call(
        "search_docs",
        cwd=cwd,
        filter={"field": "id", "op": "eq", "values": ["src/repo.py", "src/test_repo.py"]},
        view="full",
        format="json",
    )
    # 検証
    assert [item["id"] for item in implementing.data["items"]] == ["src/repo.py"]
    assert implementing.data["items"][0]["via"]["type"] == "implements"
    assert [item["id"] for item in testing.data["items"]] == ["src/test_repo.py"]
    assert testing.data["items"][0]["via"]["type"] == "tests"
    assert sorted(item["id"] for item in bodies.data["items"]) == [
        "src/repo.py",
        "src/test_repo.py",
    ]
    assert not any("related.types" in note for note in bodies.data.get("notes", []))


def _outside_logs(served: Any) -> list[str]:
    """要求のログ（標準エラー）のうち作業範囲の外を読んだ記録を返す。"""
    return [line for line in served.stderr().splitlines() if OUTSIDE_LOG in line]


def _ids(result: Any) -> list[str]:
    """JSON の結果の items の ID を並べる。"""
    return [item["id"] for item in result.data.get("items", [])]


def _tag_lines(text: str) -> str:
    """`タグ:` の行から最後までを返す。"""
    return text[text.index(TAG_HEADER) :]


def test_normal_when_outside_scope(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    commit_all: Callable[..., str],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """outside_scope: true で、scope.read に当たらない配信元を作業範囲の外として参考に読む（正常系）。"""
    # 準備
    sample = make_source("sample")
    other = make_source("other", _related_files(sample_file_set, sample_doc_text))
    renamed = sample_doc_text("doc-2", "新しい名前", description="2 件目")
    commit_all(other.folder, {"docs/doc-2.yaml": renamed}, "docs: 改名")
    served = serve(sample, other)
    cwd = str(sample.folder)
    outside = {"cwd": cwd, "source": "other", "outside_scope": True}
    # 実行
    described = served.call("describe", **outside)
    full = served.call("search_docs", view="full", **outside)
    searched = served.call("search_docs", format="json", **outside)
    traced = served.call("trace_related", from_ids=["doc-1"], format="json", **outside)
    changes = served.call("list_changes", format="json", **outside, **{"from": "HEAD~1"})
    logs = _outside_logs(served)
    without = served.call("search_docs", cwd=cwd, source="other")
    everything = served.call(
        "search_docs", cwd=cwd, source="*", outside_scope=True, view="ids", format="json"
    )
    listed = served.call("describe", cwd=cwd)
    # 検証
    assert not described.is_error
    assert described.text.splitlines()[0] == OUTSIDE_LINE
    assert full.text.splitlines()[0] == OUTSIDE_LINE
    assert full.text.count('outside_scope="true"') == 2
    assert searched.data["outside_scope"] is True
    assert _ids(searched) == ["doc-1", "doc-2"]
    assert traced.data["outside_scope"] is True
    assert _ids(traced) == ["doc-2"]
    assert changes.data["outside_scope"] is True
    assert [(item["id"], item["change"]) for item in changes.data["items"]] == [
        ("doc-2", "modified")
    ]
    assert any(cwd in line and "other" in line for line in logs)
    assert without.is_error
    assert "SourceNotReadableError" in without.text
    assert _ids(everything) == ["doc-1", "doc-2"]
    assert "other" not in everything.text
    assert "| other |" not in listed.text


def test_error_when_outside_read_disabled(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """outside_read: false の配信元は outside_scope: true でも読めないとして断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    other_files = _related_files(sample_file_set, sample_doc_text)
    other = make_source("other", other_files, outside_read=False)
    served = serve(sample, other)
    # 実行
    result = served.call("search_docs", cwd=str(sample.folder), source="other", outside_scope=True)
    # 検証
    assert result.is_error
    assert "SourceNotReadableError" in result.text
    assert "other" in result.text
    assert OUTSIDE_HINT not in result.text
    assert "1 件目" not in result.text
    assert _outside_logs(served) == []


def test_normal_when_describe_lists_refs_and_worktrees(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    run_git: Callable[..., str],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """describe(source) がブランチ・タグとワークツリーを返し、そのパスで文書を引ける（正常系）。"""
    # 準備
    sample = make_source("sample")
    run_git(sample.folder, "tag", "v0.1.0")
    worktree = add_worktree(sample.folder, "x")
    (worktree / "docs" / "doc-1.yaml").write_text(
        sample_doc_text("doc-1", "ワークツリーの文書 1"), encoding="utf-8"
    )
    served = serve(sample)
    cwd = str(sample.folder)
    # 実行
    described = served.call("describe", cwd=cwd, source="sample", format="json")
    path = described.data["worktrees"][0]["path"]
    found = served.call("search_docs", cwd=cwd, worktree=path, filter=DOC_1, view="full")
    # 検証
    assert {"develop", "feat/x"} <= set(described.data["refs"]["branches"])
    assert "v0.1.0" in described.data["refs"]["tags"]
    assert set(described.data["refs"]) == {"branches", "tags"}
    worktrees = {item["path"]: item.get("branch") for item in described.data["worktrees"]}
    assert worktrees == {str(worktree): "feat/x"}
    assert "name: ワークツリーの文書 1" in found.text


def test_normal_when_tags_are_objects(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """tags[].name で取り出したタグで絞り・数え、main_tags で主題のタグを引く（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(OBJECT_TAGS_ROW),
            "schemas/rule.schema.yaml": OBJECT_TAGS_SCHEMA,
            "rules/r1.yaml": (
                "id: r1\nname: 文書 1\ntags:\n  - {name: mcp, main: true}\n  - {name: 設計}\n"
            ),
            "rules/r2.yaml": (
                "id: r2\nname: 文書 2\ntags:\n  - {name: MCP}\n  - {name: 設計, main: true}\n"
            ),
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    arguments = {"cwd": str(sample.folder), "format": "json"}
    # 実行
    by_tags = served.call("search_docs", filter=TAG_MCP, view="summary", **arguments)
    by_main = served.call("search_docs", filter=MAIN_TAG_MCP, view="summary", **arguments)
    counted = served.call(
        "search_docs", filter=IN_RULES, view="count", group_by="tags", **arguments
    )
    picked = served.call(
        "search_docs",
        filter={"field": "id", "op": "eq", "values": ["r1"]},
        fields=["tags"],
        **arguments,
    )
    plain = served.call("search_docs", filter=DOC_1, fields=["tags"], **arguments)
    # 検証
    assert _ids(by_tags) == ["r1", "r2"]
    assert _ids(by_main) == ["r1"]
    # 表記違いの mcp・MCP は 1 つにまとめる（表記は同数なら値の昇順で先のもの）
    assert counted.data["groups"] == [{"value": "MCP", "count": 2}, {"value": "設計", "count": 2}]
    assert picked.data["items"][0]["values"]["tags"] == ["mcp", "設計"]
    assert plain.data["items"][0]["values"]["tags"] == ["a"]


def test_normal_when_term_matched_by_alias(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    sample_doc_text: Callable[..., str],
) -> None:
    """term で alias_type を持つ行の文書を name・aliases の語で引き、照合する語の一覧を返す（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(TERM_ROW),
            "schemas/term.schema.yaml": TERM_SCHEMA,
            "terms/scope.yaml": SCOPE_TERM,
            "docs/doc-1.yaml": sample_doc_text(
                "doc-1", "担当範囲の文書", description="担当範囲の説明"
            ),
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    arguments = {"cwd": str(sample.folder), "view": "ids", "format": "json"}
    # 実行
    by_alias = served.call("search_docs", term="担当範囲", **arguments)
    by_name = served.call("search_docs", term="作業範囲", **arguments)
    words = served.call("list_match_words", cwd=str(sample.folder), source="sample", format="json")
    # 検証
    pairs = {(item["word"], item["id"]) for item in words.data["words"]}
    assert _ids(by_alias) == ["scope"]
    assert _ids(by_name) == ["scope"]
    assert pairs == {("作業範囲", "scope"), ("scope", "scope"), ("担当範囲", "scope")}


def test_normal_when_tag_guide_injected(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """文書の MCP の instructions がタグの付け方を案内し、注入文は instructions を指す 1 行だけを持つ（正常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    # 実行
    response = httpx.post(
        served.url(SESSION_CONTEXT),
        json={"cwd": str(sample.folder), "reason": "startup"},
        timeout=10,
    )
    initialized = httpx.post(served.url("/mcp/"), headers=MCP_HEADERS, json=INITIALIZE, timeout=10)
    # 検証
    context = response.json()["context"]
    instructions = initialized.json()["result"]["instructions"]
    assert response.status_code == 200
    assert [rule for rule in TAG_RULES if rule not in _tag_lines(instructions)] == []
    assert TAG_HEADER not in context
    assert context.splitlines().count(POINTER_LINE) == 1
    assert len(context) <= CONTEXT_MAX_CHARS


def _descriptions(response: httpx.Response) -> list[str]:
    """`tools/list` の応答のツールの description を並べる。"""
    return [tool["description"] for tool in response.json()["result"]["tools"]]


def test_normal_when_usage_guide_received(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """文書の MCP の instructions と description が、使う場面・使わない場面・ツールの順序を案内する（正常系）。"""
    # 準備
    served = serve(make_source("sample"))
    # 実行
    initialized = httpx.post(served.url("/mcp/"), headers=MCP_HEADERS, json=INITIALIZE, timeout=10)
    tools = httpx.post(served.url("/mcp/"), headers=MCP_HEADERS, json=TOOLS_LIST, timeout=10)
    # 検証
    instructions = initialized.json()["result"]["instructions"]
    descriptions = _descriptions(tools)
    texts = [instructions, *descriptions]
    assert [guide for guide in INSTRUCTIONS_GUIDES if guide not in instructions] == []
    assert len(instructions) <= INSTRUCTIONS_MAX_CHARS
    assert len(descriptions) == 7
    assert [
        text for text in descriptions if not all(guide in text for guide in DESCRIPTION_GUIDES)
    ] == []
    assert [text for text in texts if any(word in text for word in FORBIDDEN_WORDS)] == []
