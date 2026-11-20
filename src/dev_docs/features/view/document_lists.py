"""配信元と commit の組ごとの文書の一覧の保持と、リビジョンの解決。"""

from __future__ import annotations

import asyncio
import re
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from dev_docs.integrations.project_index.types import DocumentList, RefList

# 文書の一覧の保持が持つ組の上限（非機能要件の document_list_cache_size）
DOCUMENT_LIST_CACHE_SIZE: int = 4

# ブランチとタグに無いリビジョンを commit として扱う形式
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class CachedDocumentList:
    """配信元と commit の組で保持する、型にした文書の一覧と取得したときの配信元の設定のハッシュ。"""

    # 文書の一覧を型にしたときの配信元の設定のハッシュ。違えば保持を捨てて取得し直す
    config_hash: str
    documents: DocumentList


@dataclass(slots=True)
class DocumentListCache:
    """配信元と commit の組ごとに文書の一覧を最後に使用した順で持ち、取得中の問い合わせを共有する。

    待ち受けのイベントループの中だけで呼ぶため排他しない。
    """

    max_entries: int
    # 末尾が最後に使用した組
    _entries: OrderedDict[tuple[str, str], CachedDocumentList] = field(
        default_factory=OrderedDict, init=False, repr=False
    )
    # 文書の一覧の応答の本文を取得しているタスク
    _inflight: dict[tuple[str, str], asyncio.Task[Mapping[str, Any]]] = field(
        default_factory=dict, init=False, repr=False
    )

    def get(self, source_id: str, commit: str) -> CachedDocumentList | None:
        """保持した組を返却し、最後に使用した組にする。"""
        key = (source_id, commit)
        entry = self._entries.get(key)
        # 保持に無い組は None を返却する
        if entry is None:
            return None
        self._entries.move_to_end(key)
        return entry

    def put(self, source_id: str, commit: str, entry: CachedDocumentList) -> None:
        """組を保持し、上限を超えたら最も前に使用した組を捨てる。"""
        key = (source_id, commit)
        self._entries[key] = entry
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def discard(self, source_id: str, commit: str) -> None:
        """組を保持から捨てる。"""
        self._entries.pop((source_id, commit), None)

    async def fetch(
        self,
        source_id: str,
        commit: str,
        request: Callable[[], Awaitable[Mapping[str, Any]]],
    ) -> Mapping[str, Any]:
        """同じ組の文書の一覧を取得している間はその問い合わせを待ち、無ければ問い合わせを始める。"""
        key = (source_id, commit)
        task = self._inflight.get(key)
        # 取得中の問い合わせが無い: 問い合わせを始め、終わったら取得中から除外する
        if task is None:
            task = asyncio.create_task(_run(request))
            self._inflight[key] = task

            def _forget(done: asyncio.Task[Mapping[str, Any]]) -> None:
                # 後から同じ組で始めたタスクは削除しない
                if self._inflight.get(key) is done:
                    del self._inflight[key]

            task.add_done_callback(_forget)
        # 待っている取得が取り消されても、共有している問い合わせは取り消さない
        return await asyncio.shield(task)


async def _run(request: Callable[[], Awaitable[Mapping[str, Any]]]) -> Mapping[str, Any]:
    """問い合わせを、タスクにできるコルーチンにする。"""
    return await request()


def resolve_commit(refs: RefList, ref: str | None) -> str | None:
    """リビジョンを、文書の一覧の保持のキーにする commit にする（保持しないときは None）。"""
    # Git 管理外の配信元は保持しない
    if not refs.git:
        return None
    name = refs.default_ref if ref is None else ref
    # ブランチ、次にタグの名前と一致すればその commit
    for named in (*refs.branches, *refs.tags):
        if named.name == name:
            return named.commit
    # 名前に無く commit の形式なら小文字にした値。それ以外（HEAD~1 など）は保持しない
    if COMMIT_PATTERN.match(name):
        return name.lower()
    return None
