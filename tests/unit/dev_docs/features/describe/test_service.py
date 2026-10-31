from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.describe.service import describe
from dev_docs.features.describe.types import (
    DescribeRequest,
    KindSchemaResult,
    SourceGuideResult,
    SourceListResult,
)
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import DocumentTable, ServedSource, SourceConfig
from dev_docs.shared.errors import UnknownKindError, ValidationFailedError

SCHEMA_TEXT = "description: 規約の文書\ntype: object\n"


@pytest.fixture
def store(tmp_path: Path) -> DocumentStore:
    """リビジョンの書き出しを `tmp_path` に置く文書のストアを返す。"""
    return DocumentStore(SnapshotStore(tmp_path / "snapshots"))


@pytest.fixture
def folder_source(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> ServedSource:
    """スキーマのファイルと説明書を持つ Git 管理外の配信元 sample を返す。"""
    root = tmp_path / "sample"
    write_files(root, {"schemas/rule.schema.yaml": SCHEMA_TEXT})
    table = DocumentTable(
        id="rules",
        paths=["docs/*.yaml"],
        schema_path="schemas/rule.schema.yaml",
        metadata={"name": "title"},
    )
    config = make_source_config(documents=[table], instructions="着手前に規約を引く")
    return make_served_source(
        id="sample",
        root=root,
        config=config,
        schemas={"rules": {"description": "規約の文書", "type": "object"}},
    )


def _describe(
    source_registry: SourceRegistry, store: DocumentStore, cwd: Path, **request: Any
) -> SourceListResult | SourceGuideResult | KindSchemaResult:
    """作業場所 `cwd` から `describe` を呼ぶ。"""
    return describe(DescribeRequest(cwd=str(cwd), **request), registry=source_registry, store=store)


def test_describe(
    store: DocumentStore,
    folder_source: ServedSource,
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """使える配信元の一覧（正常系）。"""
    # 準備
    notes = make_served_source(
        id="notes", root=Path("/w/notes"), scope_read=[str(folder_source.root)], scope_write=[]
    )
    other = make_served_source(
        id="other", root=Path("/w/other"), scope_read=["/zzz"], scope_write=[]
    )
    registry = make_registry(folder_source, notes, other)
    # 実行
    result = _describe(registry, store, folder_source.root)
    # 検証
    assert isinstance(result, SourceListResult)
    assert result.workplace.source_id == "sample"
    assert [(item.source_id, item.access, item.current) for item in result.sources] == [
        ("sample", "write", True),
        ("notes", "read", False),
    ]


def test_describe_when_source(
    store: DocumentStore, folder_source: ServedSource, make_registry: Callable[..., SourceRegistry]
) -> None:
    """説明書と種類（正常系）。"""
    # 実行
    result = _describe(make_registry(folder_source), store, folder_source.root, source="sample")
    # 検証
    assert isinstance(result, SourceGuideResult)
    assert result.instructions == "着手前に規約を引く"
    assert [(kind.id, kind.description) for kind in result.kinds] == [("rules", "規約の文書")]


def test_describe_when_kind(
    store: DocumentStore, folder_source: ServedSource, make_registry: Callable[..., SourceRegistry]
) -> None:
    """種類のスキーマ（正常系）。"""
    # 実行
    result = _describe(
        make_registry(folder_source), store, folder_source.root, source="sample", kind="rules"
    )
    # 検証
    assert isinstance(result, KindSchemaResult)
    assert result.schema_text == SCHEMA_TEXT
    assert result.metadata == {"name": "title"}


def test_describe_when_unknown_kind(
    store: DocumentStore, folder_source: ServedSource, make_registry: Callable[..., SourceRegistry]
) -> None:
    """知らない種類（異常系）。"""
    # 実行・検証
    with pytest.raises(UnknownKindError) as exc_info:
        _describe(
            make_registry(folder_source),
            store,
            folder_source.root,
            source="sample",
            kind="no-such-kind",
        )
    assert exc_info.value.kinds == ["rules"]


@pytest.fixture
def worktree_source(
    git_repo: Callable[..., Path],
    run_git: Callable[..., str],
    sample_files: dict[str, str],
    make_served_source: Callable[..., ServedSource],
    make_source_config: Callable[..., SourceConfig],
) -> tuple[ServedSource, Path]:
    """git リポジトリの配信元 sample と、そのワークツリー x を返す。"""
    clone = git_repo(sample_files)
    worktree = clone / ".claude" / "worktrees" / "x"
    run_git(clone, "worktree", "add", "-b", "feat/x", str(worktree))
    source = make_served_source(
        id="sample",
        root=clone,
        config=make_source_config(),
        config_files=[clone / "dev-docs.yaml"],
        is_git=True,
        repo_root=clone,
        scope_write=[str(clone)],
        worktree_globs=[str(clone / ".claude" / "worktrees" / "*")],
    )
    return source, worktree


def test_describe_when_worktree(
    store: DocumentStore,
    worktree_source: tuple[ServedSource, Path],
    sample_files: dict[str, str],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """ワークツリーの設定で説明する（正常系）。"""
    # 準備
    source, worktree = worktree_source
    (worktree / "dev-docs.yaml").write_text(
        sample_files["dev-docs.yaml"] + "instructions: ワークツリーの値\n", encoding="utf-8"
    )
    # 実行
    result = _describe(make_registry(source), store, worktree, source="sample")
    # 検証
    assert isinstance(result, SourceGuideResult)
    assert result.instructions == "ワークツリーの値"


def test_describe_when_worktree_config_invalid(
    store: DocumentStore,
    worktree_source: tuple[ServedSource, Path],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """ワークツリーの設定が検証に通らない（異常系）。"""
    # 準備
    source, worktree = worktree_source
    (worktree / "dev-docs.yaml").write_text(
        "name: sample\ndocuments:\n  - id: rules\n    schema: schemas/rule.schema.yaml\n",
        encoding="utf-8",
    )
    # 実行・検証
    with pytest.raises(ValidationFailedError) as exc_info:
        _describe(make_registry(source), store, worktree, source="sample")
    assert [v.path for v in exc_info.value.violations] == ["documents[0].paths"]


def test_describe_when_refs_and_worktrees(
    store: DocumentStore,
    worktree_source: tuple[ServedSource, Path],
    run_git: Callable[..., str],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """ブランチとワークツリー（正常系）。"""
    # 準備
    source, _ = worktree_source
    run_git(source.root, "tag", "-a", "v0.1.0", "-m", "release")
    # 実行
    result = _describe(make_registry(source), store, source.root, source="sample")
    # 検証
    assert isinstance(result, SourceGuideResult)
    assert result.refs is not None
    assert {"develop", "feat/x"} <= set(result.refs["branches"])
    assert result.refs["tags"] == ["v0.1.0"]
    assert result.worktrees is not None
    assert result.worktrees[0].branch == "feat/x"
