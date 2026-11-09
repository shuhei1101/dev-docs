from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs.features.convert.decisions import decision_page_id, find_decisions
from dev_docs.features.sources.types import ServedSource, SourceConfig


def test_find_decisions(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> None:
    """1 つのフォルダにだけある ID を返却する（正常系）。"""
    # 準備
    root = tmp_path / "sample"
    write_files(
        root,
        {
            "tmp/a/.mindstella/docs/D-1.md": "# D-1\n",
            "tmp/a/.mindstella/docs/D-2.md": "# D-2 a\n",
            "tmp/b/.mindstella/docs/D-2.md": "# D-2 b\n",
            "tmp/b/.mindstella/docs/notes.md": "# メモ\n",
        },
    )
    config = make_source_config(decision_folders=["tmp/a", "tmp/b", "tmp/c"])
    source = make_served_source(root=root, config=config)
    # 実行
    result = find_decisions(source)
    # 検証
    assert result == {"D-1": root / "tmp/a/.mindstella/docs/D-1.md"}


def test_find_decisions_when_absolute_and_worktree(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> None:
    """絶対パスと、ワークツリーから配信している配信元（正常系）。"""
    # 準備
    main = tmp_path / "main"
    worktree = tmp_path / "main/.claude/worktrees/develop"
    outside = tmp_path / "outside"
    write_files(main, {"tmp/a/.mindstella/docs/D-1.md": "# D-1\n"})
    write_files(worktree, {"dev-docs.yaml": "name: sample\n"})
    write_files(outside, {".mindstella/docs/D-9.md": "# D-9\n"})
    config = make_source_config(decision_folders=["tmp/a", str(outside)])
    source = make_served_source(
        root=worktree, config=config, main_root=main, repo_root=worktree, is_git=True
    )
    # 実行
    result = find_decisions(source)
    # 検証
    assert result == {
        "D-1": main / "tmp/a/.mindstella/docs/D-1.md",
        "D-9": outside / ".mindstella/docs/D-9.md",
    }


def test_find_decisions_when_no_folders(
    make_served_source: Callable[..., ServedSource],
) -> None:
    """`decisions.folders` が無い（正常系）。"""
    # 準備
    source = make_served_source()
    # 実行
    result = find_decisions(source)
    # 検証
    assert result == {}


def test_decision_page_id() -> None:
    """検討事項の文書のパス（正常系）。"""
    # 実行
    result = decision_page_id("_decisions/D-1")
    # 検証
    assert result == "D-1"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("dev/a", id="other"),
        pytest.param("_decisions/../x", id="outside"),
        pytest.param("_decisions/d-1", id="lowercase"),
    ],
)
def test_decision_page_id_when_other(path: str) -> None:
    """検討事項の文書でないパスと、形式に合わない ID（正常系）。"""
    # 実行
    result = decision_page_id(path)
    # 検証
    assert result is None
