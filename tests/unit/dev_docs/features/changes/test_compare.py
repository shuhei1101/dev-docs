from __future__ import annotations

from dev_docs.features.changes.compare import changed_keys, diff_lines


def test_changed_keys() -> None:
    """入れ子と要素の突き合わせ（正常系）。"""
    # 準備
    before = {"name": "a", "items": [{"id": "x", "v": 1}], "updated": "d1"}
    after = {"name": "b", "items": [{"id": "x", "v": 2}], "updated": "d2"}
    # 実行
    result = changed_keys(before, after, ignore=["updated"])
    # 検証
    assert result == {"name": ("a", "b"), "items[x].v": (1, 2)}


def test_diff_lines() -> None:
    """変えた行（正常系）。"""
    # 実行
    result = diff_lines("name: 文書 1\nx: 1\n", "name: 新しい名前\nx: 1\n")
    # 検証
    assert result == "- name: 文書 1\n+ name: 新しい名前"
