from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.shared.hashing import content_hash
from dev_docs.shared.yaml_io import load_yaml

DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
REFERENCING = {"to": "doc-2", "type": "references"}
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
    "    paths: [docs/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    after_write: [list]\n"
)
SAMPLE_ROW = "  - id: sample\n    paths: [docs/*.yaml]\n    schema: schemas/sample.schema.yaml\n"
DECISIONS_ROW = (
    "  - id: decisions\n"
    "    paths: [decisions/*.yaml]\n"
    "    schema: schemas/decision.schema.yaml\n"
    "    metadata: {name: title}\n"
)


RULES_ROW = (
    "  - id: rules\n"
    "    paths: [rules/*.yaml]\n"
    "    schema: schemas/rule.schema.yaml\n"
    "    metadata:\n"
    '      tags: "tags[].name"\n'
    '      main_tags: "tags[main].name"\n'
)
RULE_SCHEMA = (
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
    "      required: [name]\n"
)
RULE_DOC = "id: rule-1\nname: 規約 1\ntags:\n  - {name: mcp, main: true}\n  - {name: 設計}\n"


def _version(path: Path) -> str:
    """文書のファイルの今のバージョン（内容のハッシュ）を返す。"""
    return content_hash(path.read_text(encoding="utf-8"))


def _update(doc_id: str, version: str, **operation: Any) -> dict[str, Any]:
    """`update` の操作を作る。"""
    return {"op": "update", "id": doc_id, "expected_version": version, **operation}


def _setup(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    files: dict[str, str] | None = None,
) -> tuple[Any, Any, Path]:
    """ワークツリー x を持つ sample を配信し、配信元・起動したサーバー・ワークツリーを返す。"""
    source = make_source("sample", files)
    worktree = add_worktree(source.folder, "x")
    return source, serve(source), worktree


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """検査に通る変更だけをワークツリーの文書に書き、クローン本体は変えない（正常系）。"""
    # 準備
    source, served, worktree = _setup(make_source, serve, add_worktree)
    target = worktree / "docs" / "doc-1.yaml"
    clone_text = (source.folder / "docs" / "doc-1.yaml").read_text(encoding="utf-8")
    commits = run_git(worktree, "rev-list", "--count", "HEAD")
    arguments = {"cwd": str(source.folder), "worktree": str(worktree)}
    before = served.call("search_docs", filter=DOC_1, view="summary", format="json", **arguments)
    read_version = before.data["items"][0]["values"]["version"]
    # 実行
    schema = served.call("describe", source="sample", kind="sample", **arguments)
    result = served.call(
        "write_docs",
        operations=[_update("doc-1", read_version, set={"name": "新しい名前"})],
        **arguments,
    )
    after = served.call("search_docs", filter=DOC_1, view="summary", format="json", **arguments)
    # 検証
    item = result.data["results"][0]
    written = load_yaml(target.read_text(encoding="utf-8"))
    assert not schema.is_error
    assert result.data["applied"] is True
    assert item["status"] == "updated"
    assert item["version"] != read_version
    assert written["name"] == "新しい名前"
    assert written["description"] == "1 件目"
    assert (source.folder / "docs" / "doc-1.yaml").read_text(encoding="utf-8") == clone_text
    assert run_git(worktree, "rev-list", "--count", "HEAD") == commits
    assert "docs/doc-1.yaml" in run_git(worktree, "status", "--porcelain")
    assert after.data["items"][0]["values"]["name"] == "新しい名前"
    assert after.data["items"][0]["values"]["version"] == item["version"]


def test_normal_when_create(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """ids.format の ID の文書を作り、generators の出力に行を加える（正常系）。"""
    # 準備
    config = sample_config_text(IDS_AND_GENERATOR).replace(SAMPLE_ROW, AFTER_WRITE_ROW)
    files = sample_file_set(**{"dev-docs.yaml": config, "scripts/list.py": LIST_SCRIPT})
    source, served, worktree = _setup(make_source, serve, add_worktree, files)
    arguments = {"cwd": str(source.folder), "worktree": str(worktree)}
    # 実行
    created = served.call(
        "write_docs",
        operations=[
            {
                "op": "create",
                "kind": "sample",
                "data": {"name": "文書 3", "description": "3 件目"},
            }
        ],
        **arguments,
    )
    bad_id = served.call(
        "write_docs",
        operations=[
            {
                "op": "create",
                "kind": "sample",
                "data": {"id": "no-prefix", "name": "文書 4"},
            }
        ],
        **arguments,
    )
    # 検証
    item = created.data["results"][0]
    assert not created.is_error
    assert item["status"] == "created"
    assert item["id"] == "sample-3"
    assert item["version"]
    assert (worktree / "docs" / f"{item['id']}.yaml").is_file()
    assert item["id"] in (worktree / "generated" / "list.txt").read_text(encoding="utf-8")
    assert bad_id.is_error
    assert "ids.format" in bad_id.text
    assert not (worktree / "docs" / "no-prefix.yaml").exists()


def test_normal_when_dry_run(
    make_source: Callable[..., Any], serve: Callable[..., Any], add_worktree: Callable[..., Path]
) -> None:
    """dry_run: true で、書いた場合の結果と差分だけを返す（正常系）。"""
    # 準備
    source, served, worktree = _setup(make_source, serve, add_worktree)
    target = worktree / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    # 実行
    result = served.call(
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


def test_normal_when_non_git_source(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
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
    served = serve(sample, memo)
    arguments = {"cwd": str(sample.folder), "source": "memo"}
    # 実行
    created = served.call(
        "write_docs",
        operations=[{"op": "create", "kind": "sample", "data": {"name": "メモ 1"}}],
        **arguments,
    )
    created_item = created.data["results"][0]
    target = memo.folder / "docs" / f"{created_item['id']}.yaml"
    first = load_yaml(target.read_text(encoding="utf-8"))
    updated = served.call(
        "write_docs",
        operations=[
            _update(created_item["id"], created_item["version"], set={"description": "追記"})
        ],
        **arguments,
    )
    second = load_yaml(target.read_text(encoding="utf-8"))
    ordered = served.call(
        "search_docs", order_by=[{"field": "updated"}], format="json", **arguments
    )
    # 検証
    assert created_item["status"] == "created"
    assert first["created"]
    assert first["updated"]
    assert updated.data["results"][0]["status"] == "updated"
    assert second["created"] == first["created"]
    assert str(second["updated"]) > str(first["updated"])
    assert not ordered.is_error


def test_normal_when_delete_unlink(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """on_referenced: unlink で参照元の related から外して消す（正常系）。"""
    # 準備
    files = sample_file_set(
        **{"docs/doc-1.yaml": sample_doc_text("doc-1", "文書 1", related=[REFERENCING])}
    )
    source, served, worktree = _setup(make_source, serve, add_worktree, files)
    target = worktree / "docs" / "doc-2.yaml"
    referrer = worktree / "docs" / "doc-1.yaml"
    # 実行
    result = served.call(
        "delete_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        targets=[{"id": "doc-2", "expected_version": _version(target)}],
        on_referenced="unlink",
    )
    # 検証
    assert not target.exists()
    assert not load_yaml(referrer.read_text(encoding="utf-8")).get("related")
    assert result.data["unlinked"] == [{"id": "doc-1", "version": _version(referrer)}]


def test_error_when_validation_failed(
    make_source: Callable[..., Any], serve: Callable[..., Any], add_worktree: Callable[..., Path]
) -> None:
    """1 件でも検査に通らなければ何も書かず、atomic: false では通る分だけを書く（異常系）。"""
    # 準備
    source, served, worktree = _setup(make_source, serve, add_worktree)
    first = worktree / "docs" / "doc-1.yaml"
    second = worktree / "docs" / "doc-2.yaml"
    first_before = first.read_text(encoding="utf-8")
    second_before = second.read_text(encoding="utf-8")
    arguments = {
        "cwd": str(source.folder),
        "worktree": str(worktree),
        "operations": [
            _update("doc-1", _version(first), set={"name": "新しい名前"}),
            _update("doc-2", _version(second), unset=["name"]),
        ],
    }
    # 実行
    atomic = served.call("write_docs", **arguments)
    atomic_text = (first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))
    partial = served.call("write_docs", atomic=False, **arguments)
    # 検証
    results = partial.data["results"]
    assert atomic.is_error
    assert "ValidationFailedError" in atomic.text
    assert "operations[1]" in atomic.text
    assert "fix" in atomic.text
    assert atomic_text == (first_before, second_before)
    assert [item["status"] for item in results] == ["updated", "failed"]
    assert results[1]["errors"][0]["path"]
    assert load_yaml(first.read_text(encoding="utf-8"))["name"] == "新しい名前"
    assert second.read_text(encoding="utf-8") == second_before


def test_error_when_source_not_writable(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """scope.write に当たらない配信元には書き込めず、消せない（異常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    target = notes.folder / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    # 実行
    written = served.call(
        "write_docs",
        cwd=str(sample.folder),
        source="notes",
        operations=[_update("doc-1", _version(target), set={"name": "新しい名前"})],
    )
    deleted = served.call(
        "delete_docs",
        cwd=str(sample.folder),
        source="notes",
        targets=[{"id": "doc-1", "expected_version": _version(target)}],
    )
    # 検証
    for result in (written, deleted):
        assert result.is_error
        assert "SourceNotWritableError" in result.text
        assert "notes" in result.text
        assert "sample" in result.text
    assert target.read_text(encoding="utf-8") == before


def test_error_when_target_is_clone(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """Git の配信元のクローン本体には書かない（異常系）。"""
    # 準備
    source = make_source("sample")
    served = serve(source)
    target = source.folder / "docs" / "doc-1.yaml"
    before = target.read_text(encoding="utf-8")
    # 実行
    result = served.call(
        "write_docs",
        cwd=str(source.folder),
        operations=[_update("doc-1", _version(target), set={"name": "新しい名前"})],
    )
    # 検証
    assert result.is_error
    assert "TargetIsCloneError" in result.text
    assert "worktree" in result.text
    assert target.read_text(encoding="utf-8") == before


def test_error_when_delete_referenced(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """参照されている文書を on_referenced: fail で消すと断る（異常系）。"""
    # 準備
    files = sample_file_set(
        **{"docs/doc-1.yaml": sample_doc_text("doc-1", "文書 1", related=[REFERENCING])}
    )
    source, served, worktree = _setup(make_source, serve, add_worktree, files)
    target = worktree / "docs" / "doc-2.yaml"
    referrer = worktree / "docs" / "doc-1.yaml"
    before = (target.read_text(encoding="utf-8"), referrer.read_text(encoding="utf-8"))
    # 実行
    result = served.call(
        "delete_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        targets=[{"id": "doc-2", "expected_version": _version(target)}],
    )
    # 検証
    assert result.is_error
    assert "DocumentReferencedError" in result.text
    assert "doc-1" in result.text
    assert "unlink" in result.text
    assert (target.read_text(encoding="utf-8"), referrer.read_text(encoding="utf-8")) == before


def test_error_when_placement_excluded(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """置き場所のファイル名が exclude に当たる create を断る（異常系）。"""
    # 準備
    rule_row = (
        "  - id: rule\n"
        "    paths: [docs/rule/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
        "    exclude: [index.yaml]\n"
    )
    files = sample_file_set(**{"dev-docs.yaml": sample_config_text(rule_row)})
    source, served, worktree = _setup(make_source, serve, add_worktree, files)
    # 実行
    result = served.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[{"op": "create", "kind": "rule", "id": "index", "data": {"name": "目次"}}],
    )
    # 検証
    assert result.is_error
    assert "InvalidArgumentError" in result.text
    assert "operations[0].kind" in result.text
    assert "docs/rule/index.yaml" in result.text
    assert "exclude" in result.text
    assert "fix" in result.text
    assert not (worktree / "docs" / "rule" / "index.yaml").exists()


def test_normal_when_metadata_mapped(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """共通のキー名で書く（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(DECISIONS_ROW),
            "schemas/decision.schema.yaml": "type: object\nrequired: [id, title]\n",
            "decisions/d1.yaml": "id: d1\ntitle: 決定 1\n",
        }
    )
    source, served, worktree = _setup(make_source, serve, add_worktree, files)
    target = worktree / "decisions" / "d1.yaml"
    arguments = {"cwd": str(source.folder), "worktree": str(worktree)}
    # 実行
    renamed = served.call(
        "write_docs",
        operations=[_update("d1", _version(target), set={"name": "新しい名前"})],
        **arguments,
    )
    renamed_text = target.read_text(encoding="utf-8")
    searched = served.call(
        "search_docs",
        filter={"field": "id", "op": "eq", "values": ["d1"]},
        view="summary",
        format="json",
        **arguments,
    )
    created = served.call(
        "write_docs",
        operations=[{"op": "create", "kind": "decisions", "id": "d2", "data": {"name": "決定 2"}}],
        **arguments,
    )
    created_text = (worktree / "decisions" / "d2.yaml").read_text(encoding="utf-8")
    by_column = served.call(
        "write_docs",
        operations=[_update("d1", _version(target), set={"title": "別の名前"})],
        **arguments,
    )
    by_column_text = target.read_text(encoding="utf-8")
    # 検証
    assert not renamed.is_error
    assert "title: 新しい名前" in renamed_text
    assert "name:" not in renamed_text
    assert searched.data["items"][0]["values"]["name"] == "新しい名前"
    assert not created.is_error
    assert "title: 決定 2" in created_text
    assert "name:" not in created_text
    assert not by_column.is_error
    assert "title: 別の名前" in by_column_text
    assert "name:" not in by_column_text


def _write_tags(served: Any, source: Any, worktree: Path, step: dict[str, Any]) -> tuple[Any, Any]:
    """rules の規約 1 に update を 1 回当て、結果と書いた後の tags を返す。"""
    target = worktree / "rules" / "rule-1.yaml"
    result = served.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[_update("rule-1", _version(target), **step)],
    )
    return result, load_yaml(target.read_text(encoding="utf-8"))["tags"]


def test_normal_when_tags_are_objects(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """tags[].name の読み替えで、tags・main_tags への操作を name を持つオブジェクトの配列へ書き戻す（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(RULES_ROW),
            "schemas/rule.schema.yaml": RULE_SCHEMA,
            "rules/rule-1.yaml": RULE_DOC,
        }
    )
    source, served, worktree = _setup(make_source, serve, add_worktree, files)
    # 実行
    first, tags_1 = _write_tags(
        served,
        source,
        worktree,
        {"add_to": {"tags": ["テスト"]}, "remove_from": {"tags": ["設計"]}},
    )
    second, tags_2 = _write_tags(served, source, worktree, {"set": {"tags": ["mcp", "運用"]}})
    third, tags_3 = _write_tags(served, source, worktree, {"set": {"main_tags": ["運用"]}})
    # 検証
    assert not first.is_error
    assert tags_1 == [{"name": "mcp", "main": True}, {"name": "テスト"}]
    assert not second.is_error
    assert tags_2 == [{"name": "mcp", "main": True}, {"name": "運用"}]
    assert not third.is_error
    assert tags_3 == [{"name": "mcp"}, {"name": "運用", "main": True}]
