from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.shared.hashing import content_hash
from dev_docs.shared.yaml_io import load_yaml

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    type: yaml\n"
IDS_AND_GENERATOR = (
    "ids:\n"
    '  format: "{kind}-{slug}"\n'
    "generators:\n"
    "  - id: list\n"
    "    run: [python3, scripts/list.py]\n"
)
LIST_SCRIPT = (
    "import pathlib\n"
    "names = sorted(path.stem for path in pathlib.Path('docs').glob('*.yaml'))\n"
    "out = pathlib.Path('generated')\n"
    "out.mkdir(exist_ok=True)\n"
    "(out / 'list.txt').write_text('\\n'.join(names) + '\\n')\n"
)
AFTER_WRITE_ROW = (
    "  - id: sample\n"
    "    type: yaml\n"
    "    paths: [docs/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    after_write: [list]\n"
)


def _version(path: Path) -> str:
    """文書のファイルの今のバージョン（内容のハッシュ）を返す。"""
    return content_hash(path.read_text(encoding="utf-8"))


def _update(doc_id: str, version: str, **operation: Any) -> dict[str, Any]:
    """`update` の操作を作る。"""
    return {"op": "update", "id": doc_id, "expected_version": version, **operation}


def _setup(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    files: dict[str, str] | None = None,
) -> tuple[Any, Any, Path]:
    """ワークツリー x を持つ sample を起動し、配信元・環境・ワークツリーを返す。"""
    source = make_source("sample", files)
    worktree = add_worktree(source.folder, "x")
    return source, make_server(source), worktree


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """ワークツリーの文書を set で部分更新する（正常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    target = worktree / "docs" / "doc-1.yaml"
    before = _version(target)
    clone_text = (source.folder / "docs" / "doc-1.yaml").read_text(encoding="utf-8")
    commits = run_git(worktree, "rev-list", "--count", "HEAD")
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[_update("doc-1", before, set={"name": "新しい名前"})],
    )
    # 検証
    item = result.data["results"][0]
    written = load_yaml(target.read_text(encoding="utf-8"))
    assert not result.is_error
    assert result.data["applied"] is True
    assert item["status"] == "updated"
    assert item["version"] != before
    assert "新しい名前" in item["diff"]
    assert written["name"] == "新しい名前"
    assert written["description"] == "1 件目"
    assert (source.folder / "docs" / "doc-1.yaml").read_text(encoding="utf-8") == clone_text
    assert run_git(worktree, "rev-list", "--count", "HEAD") == commits


def test_normal_when_create(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """create で ids.format の ID の文書を作り、generators を流す（正常系）。"""
    # 準備
    config = sample_config_text(IDS_AND_GENERATOR).replace(
        "  - id: sample\n    type: yaml\n    paths: [docs/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n",
        AFTER_WRITE_ROW,
    )
    files = sample_file_set(**{"dev-docs.yaml": config, "scripts/list.py": LIST_SCRIPT})
    source, env, worktree = _setup(make_source, make_server, add_worktree, files)
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[
            {
                "op": "create",
                "kind": "sample",
                "data": {"name": "文書 3", "description": "3 件目"},
            }
        ],
    )
    # 検証
    item = result.data["results"][0]
    created = worktree / "docs" / f"{item['id']}.yaml"
    assert not result.is_error
    assert item["status"] == "created"
    assert item["id"] == "sample-3"
    assert item["version"]
    assert created.is_file()
    assert item["id"] in (worktree / "generated" / "list.txt").read_text(encoding="utf-8")


def test_normal_when_operations_combined(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """unset・add_to・remove_from・text_edits と replace を当てる（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "docs/doc-1.yaml": sample_doc_text(
                "doc-1", "文書 1", description="元の概要文", tags=["a", "b"], weight=3
            )
        }
    )
    source, env, worktree = _setup(make_source, make_server, add_worktree, files)
    first = worktree / "docs" / "doc-1.yaml"
    second = worktree / "docs" / "doc-2.yaml"
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[
            _update(
                "doc-1",
                _version(first),
                unset=["weight"],
                add_to={"tags": ["c"]},
                remove_from={"tags": ["a"]},
                text_edits=[{"field": "description", "old": "元の", "new": "新しい"}],
            ),
            {
                "op": "replace",
                "id": "doc-2",
                "expected_version": _version(second),
                "data": {"id": "doc-2", "name": "置き換え後"},
            },
        ],
    )
    # 検証
    doc_1 = load_yaml(first.read_text(encoding="utf-8"))
    doc_2 = load_yaml(second.read_text(encoding="utf-8"))
    assert [item["status"] for item in result.data["results"]] == ["updated", "replaced"]
    assert "weight" not in doc_1
    assert doc_1["tags"] == ["b", "c"]
    assert doc_1["description"] == "新しい概要文"
    assert doc_2 == {"id": "doc-2", "name": "置き換え後"}


def test_normal_when_dry_run(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """dry_run: true で検証と差分だけを返す（正常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    target = worktree / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[_update("doc-1", _version(target), set={"name": "新しい名前"})],
        dry_run=True,
    )
    # 検証
    assert result.data["applied"] is False
    assert "新しい名前" in result.data["results"][0]["diff"]
    assert target.read_text(encoding="utf-8") == before


def test_normal_when_not_atomic(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """atomic: false で通る操作だけを書き、失敗を添字つきで返す（正常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    first = worktree / "docs" / "doc-1.yaml"
    second = worktree / "docs" / "doc-2.yaml"
    second_before = second.read_text(encoding="utf-8")
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[
            _update("doc-1", _version(first), set={"name": "新しい名前"}),
            _update("doc-2", _version(second), unset=["name"]),
        ],
        atomic=False,
    )
    # 検証
    results = result.data["results"]
    assert not result.is_error
    assert result.data["applied"] is True
    assert [item["status"] for item in results] == ["updated", "failed"]
    assert results[1]["errors"][0]["path"]
    assert results[1]["errors"][0]["rule"]
    assert results[1]["errors"][0]["fix"]
    assert load_yaml(first.read_text(encoding="utf-8"))["name"] == "新しい名前"
    assert second.read_text(encoding="utf-8") == second_before


def test_normal_when_non_git_source(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """Git 管理外の配信元に書き、created・updated を付ける（正常系）。"""
    # 準備
    sample = make_source("sample")
    memo_config = sample_config_text('ids:\n  format: "{kind}-{slug}"\n', name="memo")
    memo = make_source(
        "memo",
        sample_file_set(**{"dev-docs.yaml": memo_config}),
        git=False,
        scope_read=[sample.folder],
        scope_write=[sample.folder],
    )
    env = make_server(sample, memo)
    # 実行
    created = env.call(
        "write_docs",
        cwd=str(sample.folder),
        source="memo",
        operations=[{"op": "create", "kind": "sample", "data": {"name": "メモ 1"}}],
    )
    target = memo.folder / "docs" / f"{created.data['results'][0]['id']}.yaml"
    first = load_yaml(target.read_text(encoding="utf-8"))
    updated = env.call(
        "write_docs",
        cwd=str(sample.folder),
        source="memo",
        operations=[
            _update(
                created.data["results"][0]["id"],
                created.data["results"][0]["version"],
                set={"description": "追記"},
            )
        ],
    )
    second = load_yaml(target.read_text(encoding="utf-8"))
    # 検証
    assert created.data["results"][0]["status"] == "created"
    assert first["created"]
    assert first["updated"]
    assert updated.data["results"][0]["status"] == "updated"
    assert second["created"] == first["created"]
    assert str(second["updated"]) > str(first["updated"])


def test_error_when_validation_failed(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """1 件でも検査に通らなければ何も書かない（異常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    first = worktree / "docs" / "doc-1.yaml"
    second = worktree / "docs" / "doc-2.yaml"
    first_before = first.read_text(encoding="utf-8")
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[
            _update("doc-1", _version(first), set={"name": "新しい名前"}),
            _update("doc-2", _version(second), unset=["name"]),
        ],
    )
    # 検証
    assert result.is_error
    assert "ValidationFailedError" in result.text
    assert "operations[1]" in result.text
    assert "name" in result.text
    assert "fix" in result.text
    assert first.read_text(encoding="utf-8") == first_before


def test_error_when_source_not_writable(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """scope.write に当たらない作業場所からの書き込みを断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    env = make_server(sample, notes)
    target = notes.folder / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(sample.folder),
        source="notes",
        operations=[_update("doc-1", _version(target), set={"name": "新しい名前"})],
    )
    # 検証
    assert result.is_error
    assert "SourceNotWritableError" in result.text
    assert "notes" in result.text
    assert "sample" in result.text
    assert target.read_text(encoding="utf-8") == before


def test_error_when_target_is_clone(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """Git の配信元のクローン本体には書かない（異常系）。"""
    # 準備
    source, env, _ = _setup(make_source, make_server, add_worktree)
    target = source.folder / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        operations=[_update("doc-1", _version(target), set={"name": "新しい名前"})],
    )
    # 検証
    assert result.is_error
    assert "TargetIsCloneError" in result.text
    assert "worktree" in result.text
    assert target.read_text(encoding="utf-8") == before


def test_error_when_version_mismatch(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """読んだときのバージョンでは、直接編集した内容を上書きしない（異常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    target = worktree / "docs" / "doc-1.yaml"
    read_version = _version(target)
    arguments = {"cwd": str(source.folder), "worktree": str(worktree), "session_id": "s1"}
    env.call(
        "search_docs",
        filter={"field": "id", "op": "eq", "values": ["doc-1"]},
        view="full",
        **arguments,
    )
    edited = sample_doc_text("doc-1", "文書 1", description="直接編集した概要文", tags=["a"])
    target.write_text(edited, encoding="utf-8")
    # 実行
    mismatch = env.call(
        "write_docs",
        operations=[_update("doc-1", read_version, set={"name": "新しい名前"})],
        **arguments,
    )
    retried = env.call(
        "write_docs",
        operations=[_update("doc-1", _version(target), set={"name": "新しい名前"})],
        **arguments,
    )
    # 検証
    written = load_yaml(target.read_text(encoding="utf-8"))
    assert mismatch.is_error
    assert "VersionMismatchError" in mismatch.text
    assert _version_of(edited) in mismatch.text
    assert "直接編集した概要文" in mismatch.text
    assert retried.data["results"][0]["status"] == "updated"
    assert written["name"] == "新しい名前"
    assert written["description"] == "直接編集した概要文"


def _version_of(text: str) -> str:
    """文書の内容のバージョンを返す。"""
    return content_hash(text)


def test_error_when_unknown_kind(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """配信元に無い kind の create を断る（異常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    files = sorted(path.name for path in (worktree / "docs").iterdir())
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[{"op": "create", "kind": "no-such-kind", "data": {"name": "x"}}],
    )
    # 検証
    assert result.is_error
    assert "UnknownKindError" in result.text
    assert "no-such-kind" in result.text
    assert "sample" in result.text
    assert sorted(path.name for path in (worktree / "docs").iterdir()) == files


def test_error_when_document_not_found(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """無い id の update を断る（異常系）。"""
    # 準備
    source, env, worktree = _setup(make_source, make_server, add_worktree)
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[_update("doc-l", "000000", set={"name": "x"})],
    )
    # 検証
    assert result.is_error
    assert "DocumentNotFoundError" in result.text
    assert "doc-l" in result.text
    assert "doc-1" in result.text


def test_error_when_invalid_argument(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """件数の上限・必須のキー・text_edits の一致を確かめる（異常系）。"""
    # 準備
    files = sample_file_set(
        **{"docs/doc-1.yaml": sample_doc_text("doc-1", "文書 1", description="重複 重複")}
    )
    source, env, worktree = _setup(make_source, make_server, add_worktree, files)
    target = worktree / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    arguments = {"cwd": str(source.folder), "worktree": str(worktree)}
    version = _version(target)
    # 実行
    too_many = env.call(
        "write_docs",
        operations=[_update("doc-1", version, set={"name": "x"})] * 51,
        **arguments,
    )
    no_version = env.call(
        "write_docs",
        operations=[{"op": "update", "id": "doc-1", "set": {"name": "x"}}],
        **arguments,
    )
    ambiguous = env.call(
        "write_docs",
        operations=[
            _update(
                "doc-1",
                version,
                text_edits=[{"field": "description", "old": "重複", "new": "一意"}],
            )
        ],
        **arguments,
    )
    # 検証
    assert too_many.is_error
    assert "50" in too_many.text
    assert no_version.is_error
    assert "operations[0].expected_version" in no_version.text
    assert ambiguous.is_error
    assert "2" in ambiguous.text
    assert "replace_all" in ambiguous.text
    assert target.read_text(encoding="utf-8") == before


def test_error_when_source_not_served(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """起動時の検証で外した配信元への書き込みを断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source(
        "broken",
        {"dev-docs.yaml": BROKEN_CONFIG},
        scope_read=[sample.folder],
        scope_write=[sample.folder],
    )
    env = make_server(sample, broken)
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(sample.folder),
        source="broken",
        operations=[_update("doc-1", "000000", set={"name": "x"})],
    )
    # 検証
    assert result.is_error
    assert "SourceNotServedError" in result.text
    assert "broken" in result.text
    assert "documents[0].paths" in result.text


def test_error_when_worktree_not_matched(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    tmp_path: Path,
) -> None:
    """worktrees に当たらない worktree を断る（異常系）。"""
    # 準備
    source, env, _ = _setup(make_source, make_server, add_worktree)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    # 実行
    result = env.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(elsewhere),
        operations=[_update("doc-1", "000000", set={"name": "x"})],
    )
    # 検証
    assert result.is_error
    assert "WorktreeNotMatchedError" in result.text
    assert str(elsewhere) in result.text
    assert ".claude/worktrees" in result.text
    assert list(elsewhere.iterdir()) == []


def test_normal_when_tool_description(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """ツールの説明に、範囲のファイルの増減・改名で管理用の YAML の行を修正することを含める（正常系）。"""
    # 準備
    env = make_server(make_source("sample"))
    # 実行
    response = env.client.post(
        "/mcp/",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    # 検証
    tools = {tool["name"]: tool for tool in response.json()["result"]["tools"]}
    assert (
        "範囲のファイルを作った・消した・改名したら、管理用の YAML の行を修正する"
        in tools["write_docs"]["description"]
    )
