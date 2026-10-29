from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dev_docs.features.access.types import Target
from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import DocumentTable, ScriptEntry, ServedSource, SourceConfig
from dev_docs.features.validation import service as service_module
from dev_docs.features.validation.service import DocumentChecker

SCHEMA = {"type": "object", "required": ["name"]}


def _script(violations: list[Any], exit_code: int = 0) -> list[str]:
    """決めた違反の JSON を出して終わるコマンドを返す。"""
    code = f"import json, sys; print(json.dumps({violations!r})); sys.exit({exit_code})"
    return [sys.executable, "-c", code]


def _checker(schema: dict[str, Any]) -> DocumentChecker:
    """決めたスキーマを返す文書のストアの偽物で、文書の検査を作る。"""
    store = SimpleNamespace(schema=lambda target, kind: schema)
    return DocumentChecker(store, timeout_sec=10)  # type: ignore[arg-type]


@pytest.fixture
def make_checked_target(
    tmp_path: Path,
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_target: Callable[..., Target],
) -> Callable[..., Target]:
    """検査の行を持つ配信元の読み書きの場所を作る関数を返す。"""

    def _make(
        validators: list[ScriptEntry],
        *,
        row_validators: list[str],
        **config_overrides: Any,
    ) -> Target:
        root = tmp_path / "ws"
        root.mkdir(exist_ok=True)
        table = DocumentTable(
            id="rules",
            paths=["rules/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
            validators=row_validators,
        )
        config = make_source_config(documents=[table], validators=validators, **config_overrides)
        return make_target(make_served_source(root=root, config=config))

    return _make


def test_document_checker_check(
    make_checked_target: Callable[..., Target], make_document: Callable[..., Document]
) -> None:
    """検査の順とまとめ（正常系）。"""
    # 準備
    target = make_checked_target(
        [ScriptEntry(id="v", run=_script([{"path": "x", "rule": "bad"}]), on=["write"])],
        row_validators=["v"],
    )
    document = make_document(
        data={"id": "doc-1"},
        metadata={"id": "doc-1", "related": [{"to": "a", "type": "blocks"}]},
    )
    # 実行
    result = _checker(SCHEMA).check(target, document, on="write")
    # 検証
    assert [violation.path for violation in result] == ["$", "related[0].type", "x"]


def test_document_checker_check_when_on_read(
    make_checked_target: Callable[..., Target],
    make_document: Callable[..., Document],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通す時点と控え（正常系）。"""
    # 準備
    calls: list[list[str]] = []
    real = service_module.run_script

    def counting(run: Any, **kwargs: Any) -> Any:
        calls.append(list(run))
        return real(run, **kwargs)

    monkeypatch.setattr(service_module, "run_script", counting)
    read_run = _script([])
    target = make_checked_target(
        [
            ScriptEntry(id="on-read", run=read_run, on=["read"]),
            ScriptEntry(id="on-write", run=_script([{"rule": "write only"}]), on=["write"]),
        ],
        row_validators=["on-read", "on-write"],
    )
    checker = _checker({})
    document = make_document()
    # 実行
    checker.check(target, document, on="read")
    checker.check(target, document, on="read")
    # 検証
    assert calls == [read_run]


def test_document_checker_check_when_script_fails(
    make_checked_target: Callable[..., Target], make_document: Callable[..., Document]
) -> None:
    """検査が動かない（正常系）。"""
    # 準備
    target = make_checked_target(
        [ScriptEntry(id="v", run=[sys.executable, "-c", "import sys; sys.exit(1)"], on=["write"])],
        row_validators=["v"],
    )
    # 実行
    result = _checker({}).check(target, make_document(), on="write")
    # 検証
    assert len(result) == 1
    assert "検査を実行できませんでした" in result[0].rule


def test_document_checker_check_when_new(
    make_checked_target: Callable[..., Target], make_document: Callable[..., Document]
) -> None:
    """新しい文書の ID（正常系）。"""
    # 準備
    target = make_checked_target([], row_validators=[], ids_format="{kind}-{slug}")
    document = make_document(id="X", metadata={"id": "X"})
    checker = _checker({})
    # 実行
    for_new = checker.check(target, document, on="write", new=True)
    for_existing = checker.check(target, document, on="write", new=False)
    # 検証
    assert [violation.path for violation in for_new] == ["id"]
    assert for_existing == []
