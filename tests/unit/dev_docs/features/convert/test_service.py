from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dev_docs.features.access.types import Target
from dev_docs.features.convert import service as service_module
from dev_docs.features.convert.service import ConvertService
from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import DocumentTable, ScriptEntry, ServedSource, SourceConfig
from dev_docs.integrations.scripts import ScriptResult

ITEMS_SCHEMA = {
    "properties": {
        "name": {"type": "string"},
        "items": {
            "type": "array",
            "x-heading": "一覧",
            "x-shape": "table",
            "items": {"type": "object", "properties": {"id": {"title": "ID"}}},
        },
    }
}


def _service(tmp_path: Path, schema: dict[str, Any], timeout_sec: float = 10) -> ConvertService:
    """決めたスキーマを返す文書のストアの偽物で、変換を作る。"""
    store = SimpleNamespace(schema=lambda target, kind: schema)
    return ConvertService(tmp_path / "converted", store, timeout_sec)  # type: ignore[arg-type]


@pytest.fixture
def make_converted_target(
    tmp_path: Path,
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
) -> Callable[..., Target]:
    """変換の設定を持つ文書の行の読み書きの場所を作る関数を返す。"""

    def _make(
        *, body_file: bool = False, converter: str | None = None, converters: list[ScriptEntry]
    ) -> Target:
        root = tmp_path / "ws"
        root.mkdir(exist_ok=True)
        table = DocumentTable(
            id="rules",
            paths=["rules/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
            converter=converter,
            records="files" if body_file else None,
            body_file="path" if body_file else None,
        )
        config = make_source_config(documents=[table], converters=converters)
        return make_target(make_served_source(root=root, config=config))

    return _make


def test_convert_service_convert(
    tmp_path: Path,
    make_converted_target: Callable[..., Target],
    make_document: Callable[..., Document],
) -> None:
    """スキーマ駆動（正常系）。"""
    # 準備
    target = make_converted_target(converters=[])
    document = make_document(data={"name": "N", "items": [{"id": "a"}]})
    # 実行
    result = _service(tmp_path, ITEMS_SCHEMA).convert(target, document)
    # 検証
    assert result.failure is None
    assert result.markdown.startswith("# N")
    assert "dev-docs-table" not in result.markdown
    assert result.table_keys == ["rules:items"]


def test_convert_service_convert_when_converter(
    tmp_path: Path,
    make_converted_target: Callable[..., Target],
    make_document: Callable[..., Document],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """スクリプトで変換し、2 回目は控えを使う（正常系）。"""
    # 準備
    calls: list[list[str]] = []

    def fake_run_script(run: Any, **kwargs: Any) -> ScriptResult:
        calls.append(list(run))
        return ScriptResult(stdout="# 変換した\n", stderr="")

    monkeypatch.setattr(service_module, "run_script", fake_run_script)
    target = make_converted_target(
        converter="c", converters=[ScriptEntry(id="c", run=["python3", "scripts/c.py"])]
    )
    service = _service(tmp_path, {})
    document = make_document()
    # 実行
    first = service.convert(target, document)
    second = service.convert(target, document)
    # 検証
    assert first.markdown.startswith("# 変換した")
    assert second.markdown.startswith("# 変換した")
    assert len(calls) == 1


def test_convert_service_convert_when_timeout(
    tmp_path: Path,
    make_converted_target: Callable[..., Target],
    make_document: Callable[..., Document],
) -> None:
    """制限時間を超える（異常系）。"""
    # 準備
    run = [sys.executable, "-c", "import time; time.sleep(5)"]
    target = make_converted_target(converter="c", converters=[ScriptEntry(id="c", run=run)])
    # 実行
    result = _service(tmp_path, {}, timeout_sec=1).convert(target, make_document())
    # 検証
    assert result.failure is not None
    assert result.failure.reason == "timeout"
    assert result.failure.script == " ".join(run)
    assert "1" in result.failure.detail


def test_convert_service_convert_when_markdown(
    tmp_path: Path,
    make_converted_target: Callable[..., Target],
    make_document: Callable[..., Document],
) -> None:
    """Markdown の本文（正常系）。"""
    # 準備
    target = make_converted_target(body_file=True, converters=[])
    markdown = make_document(body="# 本文\n\n段落\n", body_path="docs/a.md")
    code = make_document(
        data={"name": "部品", "path": "a.py"}, body="a = 1\n", body_path="src/a.py"
    )
    service = _service(tmp_path, ITEMS_SCHEMA)
    # 実行
    markdown_result = service.convert(target, markdown)
    code_result = service.convert(target, code)
    # 検証
    assert markdown_result.markdown == "# 本文\n\n段落\n"
    assert code_result.markdown.startswith("# 部品")
