from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from dev_docs.features.access.types import Target
from dev_docs.features.documents.types import Document
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import ServedSource, SourceConfig
from dev_docs.features.view.paths import page_path, parse_screen_path, screen_target
from dev_docs.features.view.types import ScreenPath


def test_parse_screen_path() -> None:
    """リビジョンつき（正常系）。"""
    # 実行
    result = parse_screen_path("sample@feat/a", "docs/x/")
    # 検証
    assert result == ScreenPath("sample", "feat/a", "docs/x")


def test_page_path(make_document: Callable[..., Document]) -> None:
    """ファイルと records（正常系）。"""
    # 準備
    plain = make_document(id="a", path="docs/a.yaml")
    record = make_document(id="r-1", path="docs/rules.yaml", record_index=0)
    # 実行
    plain_result = page_path(plain)
    record_result = page_path(record)
    # 検証
    assert plain_result == "docs/a"
    assert record_result == "docs/rules/r-1"


def test_screen_target(
    git_repo: Callable[..., Path],
    run_git: Callable[..., str],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """既定のリビジョン（正常系）。"""
    # 準備
    root = git_repo({"docs/a.yaml": "id: a\n"})
    source = make_served_source(
        id="sample",
        root=root,
        is_git=True,
        repo_root=root,
        config=make_source_config(default_ref="develop"),
    )
    commit = run_git(root, "rev-parse", "develop").strip()
    # 実行
    target, resolved = screen_target("sample", None, registry=make_registry(source))
    # 検証
    assert isinstance(target, Target)
    assert target.ref == commit
    assert resolved is not None
    assert resolved.commit == commit


def test_screen_target_when_not_git(
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """Git 管理外（正常系）。"""
    # 準備
    source = make_served_source(id="notes", is_git=False)
    # 実行
    target, resolved = screen_target("notes", "main", registry=make_registry(source))
    # 検証
    assert target.ref is None
    assert resolved is None
