from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.access.types import Target
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import LastRead, SessionKey
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import (
    DocumentTable,
    ScriptEntry,
    ServedSource,
    SourceConfig,
)
from dev_docs.features.validation.service import DocumentChecker
from dev_docs.features.write.locks import SourceLocks
from dev_docs.features.write.service import check_version, delete_docs, write_docs
from dev_docs.features.write.types import (
    DeleteRequest,
    DeleteResult,
    DeleteTarget,
    Operation,
    WriteRequest,
    WriteResult,
)
from dev_docs.shared.errors import (
    DeleteNotAllowedError,
    DocumentReferencedError,
    InvalidArgumentError,
    ValidationFailedError,
    VersionMismatchError,
)
from dev_docs.shared.hashing import content_hash, value_hash

DOC_1 = "id: doc-1\nname: 文書 1\n"
DOC_2 = "id: doc-2\nname: 文書 2\n"
SCHEMA = "title: rule\ntype: object\nrequired: [id, name]\n"


@dataclass
class WriteEnv:
    """書き込みに渡す部品と、作業場所・書き込み先のフォルダ。"""

    registry: SourceRegistry
    store: DocumentStore
    checker: DocumentChecker
    seen: SeenStore
    locks: SourceLocks
    source: ServedSource
    clone: Path
    worktree: Path

    def write(self, now: datetime | None = None, **request: Any) -> WriteResult:
        return write_docs(
            WriteRequest(cwd=str(self.worktree), **request),
            registry=self.registry,
            store=self.store,
            checker=self.checker,
            seen=self.seen,
            locks=self.locks,
            timeout_sec=10,
            now=now,
        )

    def delete(self, **request: Any) -> DeleteResult:
        return delete_docs(
            DeleteRequest(cwd=str(self.worktree), **request),
            registry=self.registry,
            store=self.store,
            checker=self.checker,
            locks=self.locks,
            timeout_sec=10,
        )


@pytest.fixture
def make_env(
    tmp_path: Path,
    git_repo: Callable[..., Path],
    run_git: Callable[..., str],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> Callable[..., WriteEnv]:
    """git リポジトリとそのワークツリー x を持つ配信元と、書き込みの部品を作る関数を返す。"""

    def _make(
        files: dict[str, str] | None = None,
        *,
        tables: list[DocumentTable] | None = None,
        generators: list[ScriptEntry] | None = None,
        **config_overrides: Any,
    ) -> WriteEnv:
        clone = git_repo(
            files
            or {
                "docs/rule/doc-1.yaml": DOC_1,
                "docs/rule/doc-2.yaml": DOC_2,
                "schemas/rule.schema.yaml": SCHEMA,
            }
        )
        worktree = clone / ".claude" / "worktrees" / "x"
        run_git(clone, "worktree", "add", "-b", "feat/x", str(worktree))
        rows = tables or [
            DocumentTable(
                id="rules",
                type="yaml",
                paths=["docs/rule/*.yaml"],
                schema_path="schemas/rule.schema.yaml",
            )
        ]
        config = make_source_config(documents=rows, generators=generators or [], **config_overrides)
        source = make_served_source(
            id="sample",
            root=clone,
            config=config,
            is_git=True,
            repo_root=clone,
            scope_write=[str(clone)],
            worktree_globs=[str(clone / ".claude" / "worktrees" / "*")],
            schemas={"rules": {"type": "object", "required": ["id", "name"]}},
        )
        store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
        return WriteEnv(
            registry=make_registry(source),
            store=store,
            checker=DocumentChecker(store, timeout_sec=10),
            seen=SeenStore(tmp_path / "seen.sqlite3", retention_days=7),
            locks=SourceLocks(),
            source=source,
            clone=clone,
            worktree=worktree,
        )

    return _make


def test_check_version_when_fields(make_document: Callable[..., Document]) -> None:
    """項目ごとのハッシュ（正常系）。"""
    # 準備
    document = make_document(data={"id": "doc-1", "name": "変えた名前", "description": "同じ"})
    expected = {"description": value_hash("同じ")}
    # 実行・検証
    check_version(document, expected, last_read=None)


def test_check_version_when_mismatch(make_document: Callable[..., Document]) -> None:
    """違うバージョン（異常系）。"""
    # 準備
    document = make_document(version="new123", body="id: doc-1\nname: 新しい\n")
    last_read = LastRead(
        doc_id="doc-1",
        version="old123",
        doc_kind="rules",
        content="id: doc-1\nname: 古い\n",
        read_at=datetime(2026, 10, 28, tzinfo=UTC),
    )
    # 実行・検証
    with pytest.raises(VersionMismatchError) as exc_info:
        check_version(document, "old123", last_read=last_read)
    assert exc_info.value.current == "new123"
    assert "- name: 古い" in exc_info.value.diff
    assert "+ name: 新しい" in exc_info.value.diff


def test_write_docs(make_env: Callable[..., WriteEnv], run_git: Callable[..., str]) -> None:
    """ワークツリーへの部分更新（正常系）。"""
    # 準備
    env = make_env()
    operation = Operation(
        op="update", id="doc-1", expected_version=content_hash(DOC_1), set={"name": "新しい名前"}
    )
    # 実行
    result = env.write(operations=[operation])
    # 検証
    changed = (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8")
    assert result.applied is True
    assert result.results[0].status == "updated"
    assert changed == "id: doc-1\nname: 新しい名前\n"
    assert (env.clone / "docs/rule/doc-1.yaml").read_text(encoding="utf-8") == DOC_1
    assert run_git(env.worktree, "rev-list", "--count", "HEAD").strip() == "1"


def test_write_docs_when_create(make_env: Callable[..., WriteEnv]) -> None:
    """ID を作って生成を動かす（正常系）。"""
    # 準備
    code = "import pathlib, sys; pathlib.Path('index.log').open('a').write('ran\\n')"
    generators = [ScriptEntry(id="index", run=[sys.executable, "-c", code])]
    table = DocumentTable(
        id="rules",
        type="yaml",
        paths=["docs/rule/*.yaml"],
        schema_path="schemas/rule.schema.yaml",
        after_write=["index"],
    )
    env = make_env(tables=[table], generators=generators, ids_format="{kind}-{slug}")
    operation = Operation(op="create", kind="rules", data={"name": "Doc Three"})
    # 実行
    result = env.write(operations=[operation])
    # 検証
    assert result.results[0].status == "created"
    assert result.results[0].id == "rules-doc-three"
    assert (env.worktree / "docs/rule/rules-doc-three.yaml").exists()
    assert (env.worktree / "index.log").read_text(encoding="utf-8") == "ran\n"


def test_write_docs_when_dry_run(make_env: Callable[..., WriteEnv]) -> None:
    """試しに書く（正常系）。"""
    # 準備
    env = make_env()
    operation = Operation(
        op="update", id="doc-1", expected_version=content_hash(DOC_1), set={"name": "試し"}
    )
    # 実行
    result = env.write(operations=[operation], dry_run=True)
    # 検証
    assert result.applied is False
    assert result.results[0].diff
    assert (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8") == DOC_1


def test_write_docs_when_partial(make_env: Callable[..., WriteEnv]) -> None:
    """一部だけ書く（正常系）。"""
    # 準備
    env = make_env()
    operations = [
        Operation(
            op="update", id="doc-1", expected_version=content_hash(DOC_1), set={"name": "通る"}
        ),
        Operation(op="update", id="doc-2", expected_version=content_hash(DOC_2), unset=["name"]),
    ]
    # 実行
    result = env.write(operations=operations, atomic=False)
    # 検証
    assert [item.status for item in result.results] == ["updated", "failed"]
    assert result.results[1].errors
    assert (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8") != DOC_1
    assert (env.worktree / "docs/rule/doc-2.yaml").read_text(encoding="utf-8") == DOC_2


def test_write_docs_when_not_git(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
    make_target: Callable[..., Target],
) -> None:
    """Git 管理外の日時（正常系）。"""
    # 準備
    root = tmp_path / "memo"
    write_files(root, {})
    table = DocumentTable(id="rules", type="yaml", paths=["docs/*.yaml"])
    source = make_served_source(
        id="memo", root=root, config=make_source_config(documents=[table]), scope_write=[str(root)]
    )
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    first = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    second = datetime(2026, 10, 28, 11, 0, tzinfo=UTC)

    def write(operation: Operation, now: datetime) -> WriteResult:
        return write_docs(
            WriteRequest(cwd=str(root), operations=[operation]),
            registry=make_registry(source),
            store=store,
            checker=DocumentChecker(store, timeout_sec=10),
            seen=SeenStore(tmp_path / "seen.sqlite3", retention_days=7),
            locks=SourceLocks(),
            timeout_sec=10,
            now=now,
        )

    created = write(Operation(op="create", kind="rules", data={"id": "memo-1", "name": "M"}), first)
    version = created.results[0].version
    # 実行
    write(Operation(op="update", id="memo-1", expected_version=version, set={"name": "M2"}), second)
    # 検証
    document = store.load(make_target(source)).documents[0]
    assert document.created == first
    assert document.updated == second


def test_write_docs_when_invalid(make_env: Callable[..., WriteEnv]) -> None:
    """検査に通らない（異常系）。"""
    # 準備
    env = make_env()
    operations = [
        Operation(
            op="update", id="doc-1", expected_version=content_hash(DOC_1), set={"name": "通る"}
        ),
        Operation(op="update", id="doc-2", expected_version=content_hash(DOC_2), unset=["name"]),
    ]
    # 実行・検証
    with pytest.raises(ValidationFailedError) as exc_info:
        env.write(operations=operations)
    assert exc_info.value.violations[0].index == 1
    assert (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8") == DOC_1
    assert (env.worktree / "docs/rule/doc-2.yaml").read_text(encoding="utf-8") == DOC_2


def test_write_docs_when_version_mismatch(
    make_env: Callable[..., WriteEnv], make_target: Callable[..., Target]
) -> None:
    """読んだ後に変わった（異常系）。"""
    # 準備
    env = make_env()
    target = make_target(env.source, base=env.worktree, worktree=env.worktree)
    document = env.store.get(target, ["doc-1"])[0]
    env.seen.mark_returned(SessionKey("s1"), "sample", "body", [document])
    edited = "id: doc-1\nname: 直接編集\n"
    (env.worktree / "docs/rule/doc-1.yaml").write_text(edited, encoding="utf-8")
    operation = Operation(
        op="update", id="doc-1", expected_version=document.version, set={"name": "後から"}
    )
    # 実行・検証
    with pytest.raises(VersionMismatchError) as exc_info:
        env.write(operations=[operation], session_id="s1")
    assert "+ name: 直接編集" in exc_info.value.diff
    assert (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8") == edited


def test_write_docs_when_too_many(make_env: Callable[..., WriteEnv]) -> None:
    """件数の上限（異常系）。"""
    # 準備
    env = make_env()
    operations = [
        Operation(op="update", id="doc-1", expected_version="x", set={"name": "n"})
        for _ in range(51)
    ]
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        env.write(operations=operations)
    assert exc_info.value.violations[0].path == "operations"


def _with_related() -> dict[str, str]:
    """文書 1 の `related` が文書 2 を指す配信元のファイルを返す。"""
    return {
        "docs/rule/doc-1.yaml": "id: doc-1\nname: 文書 1\nrelated:\n  - to: doc-2\n    type: references\n",
        "docs/rule/doc-2.yaml": DOC_2,
        "schemas/rule.schema.yaml": SCHEMA,
    }


def test_delete_docs(make_env: Callable[..., WriteEnv]) -> None:
    """ワークツリーから消す（正常系）。"""
    # 準備
    env = make_env()
    targets = [DeleteTarget(id="doc-2", expected_version=content_hash(DOC_2))]
    # 実行
    result = env.delete(targets=targets)
    # 検証
    assert result.results[0].status == "deleted"
    assert not (env.worktree / "docs/rule/doc-2.yaml").exists()
    assert (env.clone / "docs/rule/doc-2.yaml").exists()


def test_delete_docs_when_unlink(make_env: Callable[..., WriteEnv]) -> None:
    """参照も外す（正常系）。"""
    # 準備
    env = make_env(_with_related())
    targets = [DeleteTarget(id="doc-2", expected_version=content_hash(DOC_2))]
    # 実行
    result = env.delete(targets=targets, on_referenced="unlink")
    # 検証
    text = (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8")
    assert not (env.worktree / "docs/rule/doc-2.yaml").exists()
    assert "doc-2" not in text
    assert result.unlinked == [("doc-1", content_hash(text))]


def test_delete_docs_when_records(
    make_env: Callable[..., WriteEnv],
) -> None:
    """配列の要素を消す（正常系）。"""
    # 準備
    files = {
        "data/list.yaml": "items:\n  - id: a\n    path: a.txt\n  - id: b\n    path: b.txt\n",
        "data/a.txt": "a\n",
        "data/b.txt": "b\n",
    }
    table = DocumentTable(
        id="items", type="yaml", paths=["data/list.yaml"], records="items", body_file="path"
    )
    env = make_env(files, tables=[table])
    targets = [DeleteTarget(id="b", expected_version=value_hash({"id": "b", "path": "b.txt"}))]
    # 実行
    env.delete(targets=targets)
    # 検証
    text = (env.worktree / "data/list.yaml").read_text(encoding="utf-8")
    assert "id: a" in text
    assert "id: b" not in text
    assert (env.worktree / "data/b.txt").exists()


def test_delete_docs_when_referenced(make_env: Callable[..., WriteEnv]) -> None:
    """参照されている（異常系）。"""
    # 準備
    files = _with_related()
    env = make_env(files)
    targets = [DeleteTarget(id="doc-2", expected_version=content_hash(DOC_2))]
    # 実行・検証
    with pytest.raises(DocumentReferencedError) as exc_info:
        env.delete(targets=targets)
    assert exc_info.value.referrers == ["doc-1"]
    assert (env.worktree / "docs/rule/doc-2.yaml").read_text(encoding="utf-8") == DOC_2
    assert (env.worktree / "docs/rule/doc-1.yaml").read_text(encoding="utf-8") == files[
        "docs/rule/doc-1.yaml"
    ]


def test_delete_docs_when_not_allowed(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """削除を許していない（異常系）。"""
    # 準備
    root = tmp_path / "memo"
    write_files(root, {"docs/doc-1.yaml": DOC_1})
    table = DocumentTable(id="rules", type="yaml", paths=["docs/*.yaml"], writable=False)
    source = make_served_source(
        id="memo", root=root, config=make_source_config(documents=[table]), scope_write=[str(root)]
    )
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    request = DeleteRequest(
        cwd=str(root), targets=[DeleteTarget(id="doc-1", expected_version=content_hash(DOC_1))]
    )
    # 実行・検証
    with pytest.raises(DeleteNotAllowedError) as exc_info:
        delete_docs(
            request,
            registry=make_registry(source),
            store=store,
            checker=DocumentChecker(store, timeout_sec=10),
            locks=SourceLocks(),
            timeout_sec=10,
        )
    assert exc_info.value.kind == "rules"
