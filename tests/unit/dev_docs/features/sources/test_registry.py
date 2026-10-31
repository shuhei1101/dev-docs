from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources import registry as registry_module
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import ServedSource, SourceStatus
from dev_docs.shared.errors import SourceNotServedError, UnknownSourceError, Violation

type LoadResult = tuple[ServedSource | None, SourceStatus]


def test_source_registry_reload(
    monkeypatch: pytest.MonkeyPatch,
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
    make_served_source: Callable[..., ServedSource],
    make_status: Callable[..., SourceStatus],
) -> None:
    """状態を行の順に返す（正常系）。"""
    # 準備
    results: list[LoadResult] = [
        (make_served_source(id="a"), make_status("a", 0)),
        (
            None,
            make_status(
                "b",
                1,
                "not_served",
                errors=[Violation(path="documents[0].paths", rule="必須のキーが無い")],
            ),
        ),
        (None, make_status("c", 2, "disabled")),
    ]
    monkeypatch.setattr(registry_module, "load_source", lambda entry, *, index: results[index])
    terminal = make_terminal_config(
        sources=[make_entry(f"/tmp/{name}/dev-docs.yaml", source_id=name) for name in "abc"]
    )
    registry = SourceRegistry()
    # 実行
    statuses = registry.reload(terminal)
    # 検証
    assert [status.status for status in statuses] == ["serving", "not_served", "disabled"]
    assert len(registry.served()) == 1


def test_source_registry_reload_when_duplicate_name(
    monkeypatch: pytest.MonkeyPatch,
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
    make_served_source: Callable[..., ServedSource],
    make_status: Callable[..., SourceStatus],
) -> None:
    """既定の ID が重なる（正常系）。"""
    # 準備
    monkeypatch.setattr(
        registry_module,
        "load_source",
        lambda entry, *, index: (make_served_source(id="a"), make_status("a", index)),
    )
    terminal = make_terminal_config(
        sources=[make_entry("/tmp/x/dev-docs.yaml"), make_entry("/tmp/y/dev-docs.yaml")]
    )
    registry = SourceRegistry()
    # 実行
    statuses = registry.reload(terminal)
    # 検証
    assert statuses[1].status == "not_served"
    assert [error.path for error in statuses[1].errors] == ["sources[1].id"]


def test_source_registry_reload_when_reading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
    make_served_source: Callable[..., ServedSource],
    make_status: Callable[..., SourceStatus],
) -> None:
    """読み直しの間は古い一覧で応える（正常系）。"""
    # 準備
    old = make_served_source(id="a", root=tmp_path / "old")
    new = make_served_source(id="a", root=tmp_path / "new")
    entered = threading.Event()
    release = threading.Event()
    served: list[ServedSource] = [old, new]

    def blocking_load(entry: SourceEntry, *, index: int) -> LoadResult:
        source = served.pop(0)
        if source is new:
            entered.set()
            release.wait(timeout=5)
        return source, make_status("a", index)

    monkeypatch.setattr(registry_module, "load_source", blocking_load)
    terminal = make_terminal_config(sources=[make_entry("/tmp/a/dev-docs.yaml", source_id="a")])
    registry = SourceRegistry()
    registry.reload(terminal)
    worker = threading.Thread(target=registry.reload, args=(terminal,))
    worker.start()
    entered.wait(timeout=5)
    # 実行
    during = registry.get("a")
    release.set()
    worker.join(timeout=5)
    after = registry.get("a")
    # 検証
    assert during.root == tmp_path / "old"
    assert after.root == tmp_path / "new"


def test_source_registry_get(
    make_served_source: Callable[..., ServedSource],
    make_status: Callable[..., SourceStatus],
) -> None:
    """配信中を引く（正常系）。"""
    # 準備
    registry = SourceRegistry()
    source = make_served_source(id="a")
    registry._snapshot = ({"a": source}, [make_status("a", 0)])
    # 実行
    result = registry.get("a")
    # 検証
    assert result is source


def test_source_registry_get_when_not_served(
    make_status: Callable[..., SourceStatus],
) -> None:
    """外した配信元（異常系）。"""
    # 準備
    registry = SourceRegistry()
    errors = [Violation(path="documents[0].paths", rule="必須のキーが無い")]
    registry._snapshot = ({}, [make_status("b", 0, "not_served", errors=errors)])
    # 実行・検証
    with pytest.raises(SourceNotServedError) as exc_info:
        registry.get("b")
    assert exc_info.value.violations == errors
    assert exc_info.value.disabled is False


def test_source_registry_get_when_unknown() -> None:
    """無い配信元（異常系）。"""
    # 準備
    registry = SourceRegistry()
    # 実行・検証
    with pytest.raises(UnknownSourceError):
        registry.get("z")


def test_source_registry_get_when_default_ref_moved(
    git_repo: Callable[..., Path],
    commit_all: Callable[..., str],
    sample_files: dict[str, str],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """default_ref が進んだら組み立て直す（正常系）。"""
    # 準備
    root = git_repo(sample_files)
    terminal = make_terminal_config(
        sources=[make_entry(str(root / "dev-docs.yaml"), source_id="a")]
    )
    registry = SourceRegistry()
    registry.reload(terminal)
    commit_all(
        root,
        {
            "dev-docs.yaml": sample_files["dev-docs.yaml"]
            + "  - id: kind_a\n    paths: [docs/a/*.yaml]\n    schema: schemas/a.schema.yaml\n",
            "schemas/a.schema.yaml": "title: a\ntype: object\n",
        },
    )
    # 実行
    first = registry.get("a")
    second = registry.get("a")
    # 検証
    assert [table.id for table in first.config.documents] == ["rules", "kind_a"]
    assert second is first
