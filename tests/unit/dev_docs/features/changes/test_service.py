from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.access.types import Target
from dev_docs.features.changes.service import list_changes
from dev_docs.features.changes.types import LAST_READ_LABEL, ChangesRequest, ChangesResult
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import SessionKey
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import DocumentTable, ServedSource, SourceConfig
from dev_docs.shared.errors import InvalidArgumentError, LastReadNotFoundError

DOC_1 = "id: doc-1\nname: 文書 1\n"
DOC_2 = "id: doc-2\nname: 文書 2\n"


@dataclass
class ChangesEnv:
    """変更の一覧に渡す部品と、git リポジトリのクローン本体。"""

    registry: SourceRegistry
    store: DocumentStore
    seen: SeenStore
    source: ServedSource
    clone: Path

    def list(self, **request: Any) -> ChangesResult:
        return list_changes(
            ChangesRequest(cwd=str(self.clone), **request),
            registry=self.registry,
            store=self.store,
            seen=self.seen,
        )


@pytest.fixture
def env(
    tmp_path: Path,
    git_repo: Callable[..., Path],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> ChangesEnv:
    """文書 1・2 を commit した git リポジトリの配信元を持つ部品を返す。"""
    clone = git_repo({"docs/doc-1.yaml": DOC_1, "docs/doc-2.yaml": DOC_2})
    table = DocumentTable(id="rules", type="yaml", paths=["docs/*.yaml"])
    source = make_served_source(
        id="sample",
        root=clone,
        config=make_source_config(documents=[table]),
        is_git=True,
        repo_root=clone,
        scope_write=[str(clone)],
    )
    return ChangesEnv(
        registry=make_registry(source),
        store=DocumentStore(SnapshotStore(tmp_path / "snapshots")),
        seen=SeenStore(tmp_path / "seen.sqlite3", retention_days=7),
        source=source,
        clone=clone,
    )


def test_list_changes(
    env: ChangesEnv, commit_all: Callable[..., str], run_git: Callable[..., str]
) -> None:
    """2 つの commit の間（正常系）。"""
    # 準備
    first = run_git(env.clone, "rev-parse", "HEAD").strip()
    second = commit_all(env.clone, {"docs/doc-1.yaml": "id: doc-1\nname: 新しい名前\n"})
    # 実行
    result = env.list(**{"from": first, "to": second, "view": "full"})
    # 検証
    assert result.range_from.commit == first[:7]
    assert result.range_to.commit == second[:7]
    assert result.range_from.date is not None
    assert [(item.id, item.change, item.keys) for item in result.items] == [
        ("doc-1", "modified", ["name"])
    ]
    assert result.items[0].diff is not None
    assert "- name: 文書 1" in result.items[0].diff
    assert "+ name: 新しい名前" in result.items[0].diff


def test_list_changes_when_last_read(env: ChangesEnv, make_target: Callable[..., Target]) -> None:
    """前回読んだ時点から（正常系）。"""
    # 準備
    document = env.store.get(make_target(env.source), ["doc-1"])[0]
    env.seen.mark_returned(SessionKey("s1"), "sample", "body", [document])
    (env.clone / "docs/doc-1.yaml").write_text("id: doc-1\nname: 直接編集\n", encoding="utf-8")
    # 実行
    result = env.list(session_id="s1")
    # 検証
    assert result.range_from.input == LAST_READ_LABEL
    assert [item.id for item in result.items] == ["doc-1"]


def test_list_changes_when_added_and_deleted(
    env: ChangesEnv, commit_all: Callable[..., str], run_git: Callable[..., str]
) -> None:
    """足した文書と消した文書（正常系）。"""
    # 準備
    first = run_git(env.clone, "rev-parse", "HEAD").strip()
    second = commit_all(
        env.clone, {"docs/doc-3.yaml": "id: doc-3\nname: 文書 3\n"}, delete=("docs/doc-2.yaml",)
    )
    # 実行
    result = env.list(**{"from": first, "to": second})
    # 検証
    assert [(item.id, item.change) for item in result.items] == [
        ("doc-2", "deleted"),
        ("doc-3", "added"),
    ]


def test_list_changes_when_no_last_read(env: ChangesEnv) -> None:
    """読んだ記録が無い（異常系）。"""
    # 実行・検証
    with pytest.raises(LastReadNotFoundError):
        env.list(session_id="fresh")


def test_list_changes_when_to_without_from(env: ChangesEnv) -> None:
    """`from` の無い `to`（異常系）。"""
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        env.list(to="HEAD")
    assert exc_info.value.violations[0].path == "to"
