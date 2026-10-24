from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from dev_docs.__main__ import build_parser, main

PYPROJECT_PATH = Path(__file__).parents[3] / "pyproject.toml"


def test_build_parser() -> None:
    """コマンド名が dev-docs になる（正常系）。"""
    # 実行
    parser = build_parser()
    # 検証
    assert parser.prog == "dev-docs"


def test_main_when_version(capsys: pytest.CaptureFixture[str]) -> None:
    """バージョンを出す（正常系）。"""
    # 準備
    with PYPROJECT_PATH.open("rb") as f:
        expected_version = tomllib.load(f)["project"]["version"]
    # 実行
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    # 検証
    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"dev-docs {expected_version}\n"


def test_main_when_help(capsys: pytest.CaptureFixture[str]) -> None:
    """使い方を出す（正常系）。"""
    # 実行
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    # 検証
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.startswith("usage: dev-docs")


def test_main_when_no_command(capsys: pytest.CaptureFixture[str]) -> None:
    """サブコマンドが無い（異常系）。"""
    # 実行
    with pytest.raises(SystemExit) as exc_info:
        main([])
    # 検証
    assert exc_info.value.code == 2
    assert "cmd" in capsys.readouterr().err
