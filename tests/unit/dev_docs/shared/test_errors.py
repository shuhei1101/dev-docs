from __future__ import annotations

from dev_docs.shared.errors import (
    CrossOriginError,
    ProjectIndexUnreachableError,
    SourceNotServedError,
    Violation,
)


def test_dev_docs_error_details() -> None:
    """追加のプロパティを辞書にする（正常系）。"""
    # 準備
    error = SourceNotServedError(
        violations=[Violation(path="documents[0].paths", rule="必須のキーが無い")],
        disabled=False,
    )
    # 実行
    result = error.details()
    # 検証
    assert result == {
        "violations": [
            {
                "path": "documents[0].paths",
                "rule": "必須のキーが無い",
                "fix": "",
                "index": None,
                "doc": None,
            }
        ],
        "disabled": False,
    }


def test_dev_docs_error_details_when_no_extra() -> None:
    """追加のプロパティが無い（正常系）。"""
    # 準備
    error = CrossOriginError(message="…")
    # 実行
    result = error.details()
    # 検証
    assert result == {}


def test_project_index_unreachable_error() -> None:
    """つながらないときの本文と詳細（正常系）。"""
    # 準備
    error = ProjectIndexUnreachableError(
        address="http://127.0.0.1:8786", reason="接続を拒否されました（Connection refused）"
    )
    # 実行
    details = error.details()
    # 検証
    assert error.message == (
        "project-index（http://127.0.0.1:8786）に接続できませんでした。"
        "接続を拒否されました（Connection refused）"
    )
    assert details == {
        "address": "http://127.0.0.1:8786",
        "reason": "接続を拒否されました（Connection refused）",
    }
    assert error.status == 503
