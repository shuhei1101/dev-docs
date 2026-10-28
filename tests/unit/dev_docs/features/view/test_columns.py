from __future__ import annotations

from pathlib import Path

from dev_docs.features.view.columns import ColumnSettings


def test_save(tmp_path: Path) -> None:
    """他の表を残す（正常系）。"""
    # 準備
    settings = ColumnSettings(tmp_path / "columns")
    settings.save("sample", "a:x", ["c1", "c2"])
    settings.save("sample", "a:y", ["c3"])
    # 実行
    settings.save("sample", "a:x", [])
    result = settings.get("sample")
    # 検証
    assert result == {"a:y": ["c3"]}
