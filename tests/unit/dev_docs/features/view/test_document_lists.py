from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from dev_docs.features.view.document_lists import (
    CachedDocumentList,
    DocumentListCache,
    resolve_commit,
)
from dev_docs.integrations.project_index.types import DocumentList, NamedRef, RefList
from dev_docs.shared.errors import ProjectIndexResponseError

BODY: dict[str, Any] = {"ref": "8b1d4e0", "documents": []}


def _entry(config_hash: str = "h") -> CachedDocumentList:
    """保持する値を作る。"""
    return CachedDocumentList(
        config_hash=config_hash, documents=DocumentList(ref=None, documents=[])
    )


class _Request:
    """呼ばれた数を数え、イベントが立つまで待ってから応答の本文を返却する問い合わせの偽物。"""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls = 0
        self.release = asyncio.Event()
        self._error = error

    async def __call__(self) -> Mapping[str, Any]:
        self.calls += 1
        await self.release.wait()
        if self._error is not None:
            raise self._error
        return BODY


def test_get_when_used() -> None:
    """取り出した組を最後に使用した組にする（正常系）。"""
    # 準備
    cache = DocumentListCache(max_entries=2)
    cache.put("s", "a", _entry("a"))
    cache.put("s", "b", _entry("b"))
    # 実行
    cache.get("s", "a")
    cache.put("s", "c", _entry("c"))
    # 検証
    assert cache.get("s", "b") is None
    assert cache.get("s", "a") == _entry("a")
    assert cache.get("s", "c") == _entry("c")


def test_put_when_limit_exceeded() -> None:
    """上限を超えると最も前に使用した組を捨てる（正常系）。"""
    # 準備
    cache = DocumentListCache(max_entries=4)
    # 実行
    cache.put("s", "c1", _entry("1"))
    cache.put("s", "c2", _entry("2"))
    cache.put("s", "c3", _entry("3"))
    cache.put("s", "c4", _entry("4"))
    cache.put("s", "c5", _entry("5"))
    # 検証
    assert cache.get("s", "c1") is None
    assert cache.get("s", "c2") == _entry("2")
    assert cache.get("s", "c3") == _entry("3")
    assert cache.get("s", "c4") == _entry("4")
    assert cache.get("s", "c5") == _entry("5")


def test_fetch_when_shared() -> None:
    """同時の取得で問い合わせを 1 回にまとめる（正常系）。"""
    # 準備
    cache = DocumentListCache(max_entries=4)
    request = _Request()

    async def run() -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        first = asyncio.create_task(cache.fetch("s", "c1", request))
        second = asyncio.create_task(cache.fetch("s", "c1", request))
        await asyncio.sleep(0)
        request.release.set()
        return await first, await second

    # 実行
    first, second = asyncio.run(run())
    # 検証
    assert request.calls == 1
    assert first == BODY
    assert second == BODY
    assert cache._inflight == {}


def test_fetch_when_failed() -> None:
    """失敗を待っていた取得にも返却し、次はもう一度問い合わせる（異常系）。"""
    # 準備
    cache = DocumentListCache(max_entries=4)
    request = _Request(
        error=ProjectIndexResponseError(
            address="http://127.0.0.1:8786", status_code=500, summary="x", reason="x"
        )
    )

    async def run() -> list[BaseException | Mapping[str, Any]]:
        first = asyncio.create_task(cache.fetch("s", "c1", request))
        second = asyncio.create_task(cache.fetch("s", "c1", request))
        await asyncio.sleep(0)
        request.release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        third = await asyncio.gather(cache.fetch("s", "c1", request), return_exceptions=True)
        return [*results, *third]

    # 実行
    results = asyncio.run(run())
    # 検証
    assert isinstance(results[0], ProjectIndexResponseError)
    assert isinstance(results[1], ProjectIndexResponseError)
    assert isinstance(results[2], ProjectIndexResponseError)
    assert request.calls == 2


def test_fetch_when_waiter_cancelled() -> None:
    """先に問い合わせた取得を取り消しても共有した問い合わせは続く（正常系）。"""
    # 準備
    cache = DocumentListCache(max_entries=4)
    request = _Request()

    async def run() -> tuple[bool, Mapping[str, Any]]:
        first = asyncio.create_task(cache.fetch("s", "c1", request))
        second = asyncio.create_task(cache.fetch("s", "c1", request))
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.sleep(0)
        request.release.set()
        try:
            await first
        except asyncio.CancelledError:
            cancelled = True
        else:
            cancelled = False
        return cancelled, await second

    # 実行
    cancelled, second = asyncio.run(run())
    # 検証
    assert cancelled is True
    assert second == BODY
    assert request.calls == 1


def test_resolve_commit() -> None:
    """ブランチ・タグ・省略・commit（正常系）。"""
    # 準備
    refs = RefList(
        git=True,
        default_ref="main",
        branches=[
            NamedRef(name="main", commit="8b1d4e0"),
            NamedRef(name="abcdef1", commit="1111111"),
        ],
        tags=[NamedRef(name="v1", commit="3f2a9c1")],
    )
    # 実行
    resolved = [
        resolve_commit(refs, "main"),
        resolve_commit(refs, "v1"),
        resolve_commit(refs, None),
        resolve_commit(refs, "abcdef1"),
        resolve_commit(refs, "7EF1589"),
    ]
    # 検証
    assert resolved == ["8b1d4e0", "3f2a9c1", "8b1d4e0", "1111111", "7ef1589"]


@pytest.mark.parametrize(
    ("git", "ref"),
    [
        pytest.param(True, "HEAD~1", id="expression"),
        pytest.param(True, "feature/x", id="unknown-branch"),
        pytest.param(False, None, id="not-git"),
    ],
)
def test_resolve_commit_when_unresolvable(git: bool, ref: str | None) -> None:
    """保持を使用しないリビジョン（正常系）。"""
    # 準備
    refs = RefList(git=git, default_ref="main", branches=[NamedRef(name="main", commit="8b1d4e0")])
    # 実行
    resolved = resolve_commit(refs, ref)
    # 検証
    assert resolved is None
