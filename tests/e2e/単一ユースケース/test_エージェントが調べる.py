from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

FILES_SCHEMA = Path(__file__).parents[3] / "templates" / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
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
    "      - {to: src/repo, type: tests}\n"
)
SEARCH_WORD = {"field": "body", "op": "contains", "values": ["検索"]}
IN_ARCHIVE = {"field": "@path", "op": "glob", "values": ["notes/archive/**"]}
BY_MATCHES = {"fields": ["@matches"], "order_by": [{"field": "@matches", "direction": "desc"}]}
NOTES_A = {"field": "id", "op": "eq", "values": ["notes/a"]}
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
                "files:\n  - path: a.py\n    tags: [auth, code]\n  - path: b.py\n    name: 部品 B\n"
            ),
            "src/a.py": "a = 1\n",
            "src/b.py": "b = 2\n",
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    by_id = {"cwd": str(sample.folder), "filter": {"field": "id", "op": "eq", "values": ["src/a"]}}
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
        filter={"field": "id", "op": "eq", "values": ["src/b"]},
        view="summary",
        format="json",
    )
    markdown = served.call("search_docs", view="full", **by_id)
    as_json = served.call("search_docs", view="full", format="json", **by_id)
    # 検証
    item = tagged.data["items"][0]
    located = as_json.data["items"][0]
    assert [row["id"] for row in tagged.data["items"]] == ["src/a"]
    assert item["values"]["name"] == "a"
    assert item["values"]["tags"] == ["auth", "code"]
    assert other.data["items"][0]["values"]["name"] == "部品 B"
    assert "a = 1" in markdown.text
    assert f'<document path="{sample.folder}/src/a.py" scope="full">' in markdown.text
    assert located["path"] == f"{sample.folder}/src/a.py"
    assert located["scope"] == "full"
    assert located["values"]["path"] == "a.py"


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
        ("notes/a", 3),
        ("notes/b", 1),
    ]
    assert [(item["id"], item["values"]["@matches"]) for item in without_not.data["items"]] == [
        ("notes/a", 3),
        ("notes/archive/c", 2),
        ("notes/b", 1),
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
        "trace_related", cwd=cwd, from_ids=["src/repo"], direction="in", depth=1, format="json"
    )
    bodies = served.call(
        "search_docs",
        cwd=cwd,
        filter={"field": "id", "op": "eq", "values": ["src/repo", "src/test_repo"]},
        view="full",
        format="json",
    )
    # 検証
    assert [item["id"] for item in implementing.data["items"]] == ["src/repo"]
    assert implementing.data["items"][0]["via"]["type"] == "implements"
    assert [item["id"] for item in testing.data["items"]] == ["src/test_repo"]
    assert testing.data["items"][0]["via"]["type"] == "tests"
    assert sorted(item["id"] for item in bodies.data["items"]) == ["src/repo", "src/test_repo"]
    assert not any("related.types" in note for note in bodies.data.get("notes", []))
