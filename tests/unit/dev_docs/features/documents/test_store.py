from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.access.types import Target
from dev_docs.features.documents import store as store_module
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.sources.types import DocumentTable, ServedSource, SourceConfig
from dev_docs.shared.errors import DocumentNotFoundError, UnknownKindError

OCT_01 = "2026-10-01T12:00:00+09:00"


@pytest.fixture
def document_store(tmp_path: Path) -> DocumentStore:
    """リビジョンの書き出しを `tmp_path` に置く文書のストアを返す。"""
    return DocumentStore(SnapshotStore(tmp_path / "snapshots"))


@pytest.fixture
def workspace(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
) -> Target:
    """rules（YAML 2 件）と notes（管理用の YAML で配信する Markdown 2 件）を持つ Git の管理外の配信元の読む場所を返す。"""
    root = tmp_path / "ws"
    write_files(
        root,
        {
            "rules/a.yaml": "id: a\nname: A\n",
            "rules/b.yaml": "id: b\nname: B\n",
            "notes/files.yaml": "files:\n  - path: x.md\n  - path: y.md\n",
            "notes/x.md": "# X\n",
            "notes/y.md": "# Y\n",
        },
    )
    documents = [
        DocumentTable(id="rules", paths=["rules/*.yaml"], schema_path="schemas/rule.schema.yaml"),
        DocumentTable(
            id="notes",
            paths=["notes/files.yaml"],
            schema_path="schemas/rule.schema.yaml",
            records="files",
            body_file="path",
        ),
    ]
    source = make_served_source(root=root, config=make_source_config(documents=documents))
    return make_target(source)


def test_document_store_load(document_store: DocumentStore, workspace: Target) -> None:
    """行ごとに集める（正常系）。"""
    # 実行
    result = document_store.load(workspace)
    # 検証
    assert [(doc.kind, doc.id) for doc in result.documents] == [
        ("rules", "a"),
        ("rules", "b"),
        ("notes", "notes/x"),
        ("notes", "notes/y"),
    ]
    assert result.problems == []


def test_document_store_load_when_cached(
    document_store: DocumentStore,
    workspace: Target,
    write_files: Callable[[Path, dict[str, str]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """変わったファイルだけ読み直す（正常系）。"""
    # 準備
    calls: list[str] = []
    real = store_module.load_file

    def recording(root: Path, path: str, *args: Any, **kwargs: Any) -> Any:
        calls.append(path)
        return real(root, path, *args, **kwargs)

    monkeypatch.setattr(store_module, "load_file", recording)
    document_store.load(workspace)
    calls.clear()
    write_files(workspace.base, {"rules/a.yaml": "id: a\nname: A2 changed\n"})
    # 実行
    result = document_store.load(workspace)
    # 検証
    assert calls == ["rules/a.yaml"]
    assert result.documents[0].data["name"] == "A2 changed"


def test_document_store_load_when_deleted(document_store: DocumentStore, workspace: Target) -> None:
    """削除されたファイル（正常系）。"""
    # 準備
    document_store.load(workspace)
    (workspace.base / "rules" / "b.yaml").unlink()
    # 実行
    result = document_store.load(workspace)
    # 検証
    assert [doc.path for doc in result.documents if doc.kind == "rules"] == ["rules/a.yaml"]


def test_document_store_load_when_duplicate_id(
    document_store: DocumentStore,
    workspace: Target,
    write_files: Callable[[Path, dict[str, str]], None],
) -> None:
    """重なった ID（正常系）。"""
    # 準備
    write_files(
        workspace.base, {"rules/a.yaml": "id: x\nname: A\n", "rules/b.yaml": "id: x\nname: B\n"}
    )
    # 実行
    result = document_store.load(workspace, kinds=["rules"])
    # 検証
    assert [doc.path for doc in result.documents] == ["rules/a.yaml"]
    assert [(p.path, p.reason) for p in result.problems] == [("rules/b.yaml", "duplicate_id")]


def test_document_store_load_when_ref(
    tmp_path: Path,
    git_repo: Callable[..., Path],
    write_files: Callable[[Path, dict[str, str]], None],
    run_git: Callable[..., str],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
    document_store: DocumentStore,
) -> None:
    """過去のリビジョン（正常系）。"""
    # 準備
    root = git_repo({"rules/a.yaml": "id: a\nname: old\n"}, date=OCT_01)
    first = run_git(root, "rev-parse", "HEAD").strip()
    write_files(root, {"rules/a.yaml": "id: a\nname: new\n"})
    documents = [
        DocumentTable(id="rules", paths=["rules/*.yaml"], schema_path="schemas/rule.schema.yaml")
    ]
    source = make_served_source(
        root=root,
        is_git=True,
        repo_root=root,
        config=make_source_config(documents=documents, default_ref="develop"),
    )
    target = make_target(source, ref=first)
    # 実行
    result = document_store.load(target)
    # 検証
    assert result.documents[0].data["name"] == "old"
    assert result.documents[0].updated == datetime.fromisoformat(OCT_01)


def test_document_store_load_when_unknown_kind(
    document_store: DocumentStore, workspace: Target
) -> None:
    """無い種類（異常系）。"""
    # 実行・検証
    with pytest.raises(UnknownKindError):
        document_store.load(workspace, kinds=["x"])


def test_document_store_get(document_store: DocumentStore, workspace: Target) -> None:
    """渡した順（正常系）。"""
    # 実行
    result = document_store.get(workspace, ["b", "a"])
    # 検証
    assert [doc.id for doc in result] == ["b", "a"]


def test_document_store_get_when_missing(
    document_store: DocumentStore,
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
) -> None:
    """無い ID と近い候補（異常系）。"""
    # 準備
    root = tmp_path / "ws"
    write_files(root, {"rules/auth.yaml": "id: rule-auth\nname: Auth\n"})
    documents = [
        DocumentTable(id="rules", paths=["rules/*.yaml"], schema_path="schemas/rule.schema.yaml")
    ]
    source = make_served_source(root=root, config=make_source_config(documents=documents))
    target = make_target(source)
    # 実行・検証
    with pytest.raises(DocumentNotFoundError) as exc_info:
        document_store.get(target, ["rule-auht", "zzz"])
    assert exc_info.value.missing == ["rule-auht", "zzz"]
    assert exc_info.value.candidates["rule-auht"] == ["rule-auth"]
    assert exc_info.value.candidates["zzz"] == []


def test_document_store_schema_when_worktree(
    document_store: DocumentStore,
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
) -> None:
    """ワークツリーのスキーマ（正常系）。"""
    # 準備
    clone = tmp_path / "clone"
    worktree = tmp_path / "wt"
    write_files(clone, {"schemas/rule.schema.yaml": "type: object\nrequired: [id, name]\n"})
    write_files(worktree, {"schemas/rule.schema.yaml": "type: object\nrequired: [id]\n"})
    documents = [
        DocumentTable(
            id="rules",
            paths=["rules/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
        )
    ]
    startup = {"type": "object", "required": ["id", "name"]}
    source = make_served_source(
        root=clone,
        config=make_source_config(documents=documents),
        schemas={"rules": startup},
    )
    in_worktree = make_target(source, base=worktree, worktree=worktree)
    in_clone = make_target(source)
    # 実行
    from_worktree = document_store.schema(in_worktree, "rules")
    from_clone = document_store.schema(in_clone, "rules")
    # 検証
    assert from_worktree["required"] == ["id"]
    assert from_clone == startup


def test_document_store_schema_when_ref(
    document_store: DocumentStore,
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
) -> None:
    """`$ref` を解いて返す（正常系）。"""
    # 準備
    root = tmp_path / "ws"
    write_files(
        root,
        {
            "schemas/rule.schema.yaml": "type: object\n",
            "schemas/共通.schema.yaml": "$defs:\n  markdown:\n    type: string\n    title: Markdown\n",
        },
    )
    documents = [
        DocumentTable(
            id="rules",
            paths=["rules/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
        )
    ]
    raw = {"properties": {"body": {"$ref": "共通.schema.yaml#/$defs/markdown"}}}
    source = make_served_source(
        root=root, config=make_source_config(documents=documents), schemas={"rules": raw}
    )
    # 実行
    result = document_store.schema(make_target(source), "rules")
    # 検証
    assert result["properties"]["body"] == {"type": "string", "title": "Markdown"}


def test_document_store_invalidate(document_store: DocumentStore, workspace: Target) -> None:
    """同じ大きさ・同じ更新日時の書き換え（正常系）。"""
    # 準備
    target_file = workspace.base / "rules" / "a.yaml"
    document_store.load(workspace)
    stat = target_file.stat()
    target_file.write_text("id: a\nname: Z\n", encoding="utf-8")
    os.utime(target_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    document_store.invalidate([target_file])
    # 実行
    result = document_store.load(workspace)
    # 検証
    assert result.documents[0].data["name"] == "Z"


def test_document_store_location(
    document_store: DocumentStore,
    workspace: Target,
    tmp_path: Path,
    make_document: Callable[..., Document],
) -> None:
    """作業ツリーと body_file（正常系）。"""
    # 準備
    plain = make_document(path="rules/a.yaml", body_path=None)
    code = make_document(id="src/a", path="src/files.yaml", body_path="src/a.py")
    # 実行
    plain_location = document_store.location(workspace, plain)
    code_location = document_store.location(workspace, code)
    # 検証
    assert plain_location == str(tmp_path / "ws" / "rules" / "a.yaml")
    assert code_location == str(tmp_path / "ws" / "src" / "a.py")


def test_document_store_location_when_worktree(
    document_store: DocumentStore,
    workspace: Target,
    tmp_path: Path,
    make_target: Callable[..., Target],
    make_document: Callable[..., Document],
) -> None:
    """ワークツリー（正常系）。"""
    # 準備
    worktree = tmp_path / "ws" / ".claude" / "worktrees" / "x"
    target = make_target(workspace.source, base=worktree, worktree=worktree)
    document = make_document(path="rules/a.yaml", body_path=None)
    # 実行
    result = document_store.location(target, document)
    # 検証
    assert result == str(worktree / "rules" / "a.yaml")


def test_document_store_location_when_ref(
    document_store: DocumentStore,
    workspace: Target,
    make_target: Callable[..., Target],
    make_document: Callable[..., Document],
) -> None:
    """リビジョン（正常系）。"""
    # 準備
    target = make_target(workspace.source, ref="HEAD")
    document = make_document(path="rules/a.yaml", body_path=None)
    # 実行
    result = document_store.location(target, document)
    # 検証
    assert result is None


def _sync_source(
    root: Path,
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> ServedSource:
    """`metadata` の列の欠けを数える行 rules と、管理用の YAML の行 src を持つ配信元を返す。"""
    documents = [
        DocumentTable(
            id="rules",
            paths=["rules/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
            metadata={"name": "title"},
        ),
        DocumentTable(
            id="src",
            paths=["src/files.yaml"],
            schema_path="schemas/rule.schema.yaml",
            records="files",
            body_file="path",
        ),
    ]
    return make_served_source(root=root, config=make_source_config(documents=documents))


def test_check_sync(
    document_store: DocumentStore,
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> None:
    """3 種のずれ（正常系）。"""
    # 準備
    root = tmp_path / "ws"
    write_files(
        root,
        {
            "rules/a.yaml": "id: a\ntitle: A\n",
            "rules/b.yaml": "id: b\n",
            "src/files.yaml": "files:\n  - path: a.py\n  - path: c.py\n",
            "src/a.py": "a = 1\n",
            "src/d.py": "d = 4\n",
        },
    )
    source = _sync_source(root, make_source_config, make_served_source)
    # 実行
    report = store_module.check_sync(document_store, source)
    # 検証
    assert report.source_id == "sample"
    assert report.missing_refs == ["rules: b: name（title）"]
    assert report.unindexed_files == ["src: src/d.py"]
    assert len(report.missing_body_files) == 1
    assert report.missing_body_files[0].startswith("src/files.yaml: ")
    assert "c.py" in report.missing_body_files[0]


def test_check_sync_when_clean(
    document_store: DocumentStore,
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> None:
    """ずれが無い（正常系）。"""
    # 準備
    root = tmp_path / "ws"
    write_files(
        root,
        {
            "rules/a.yaml": "id: a\ntitle: A\n",
            "rules/b.yaml": "id: b\ntitle: B\n",
            "src/files.yaml": "files:\n  - path: a.py\n  - path: d.py\n",
            "src/a.py": "a = 1\n",
            "src/d.py": "d = 4\n",
        },
    )
    source = _sync_source(root, make_source_config, make_served_source)
    # 実行
    report = store_module.check_sync(document_store, source)
    # 検証
    assert report.missing_refs == []
    assert report.unindexed_files == []
    assert report.missing_body_files == []


def test_check_sync_when_alias_violation(
    document_store: DocumentStore,
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> None:
    """エイリアスのキーの違反（正常系）。"""
    # 準備
    root = tmp_path / "ws"
    write_files(
        root,
        {
            "terms/broken.yaml": "id: broken\nname: 壊れた用語\ndescription: 型の違う別名\naliases: 3\n"
        },
    )
    documents = [
        DocumentTable(
            id="terms",
            paths=["terms/*.yaml"],
            schema_path="schemas/term.schema.yaml",
            alias_type="term",
        )
    ]
    source = make_served_source(root=root, config=make_source_config(documents=documents))
    # 実行
    report = store_module.check_sync(document_store, source)
    # 検証
    assert [(item.doc, item.path) for item in report.alias_violations] == [
        ("terms/broken.yaml", "aliases")
    ]
