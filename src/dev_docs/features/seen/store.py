"""会話ごとの記録の SQLite への読み書き。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from dev_docs.features.documents.types import Document
from dev_docs.features.seen.types import Activity, ActivityKind, LastRead, ReturnKind, SessionKey

SEEN_SCHEMA = """\
CREATE TABLE IF NOT EXISTS returned (
  session_id TEXT NOT NULL, agent_id TEXT NOT NULL, source_id TEXT NOT NULL,
  kind TEXT NOT NULL, doc_id TEXT NOT NULL, version TEXT NOT NULL,
  doc_kind TEXT NOT NULL, content TEXT, at TEXT NOT NULL,
  PRIMARY KEY (session_id, agent_id, source_id, kind, doc_id));
CREATE TABLE IF NOT EXISTS activity (
  session_id TEXT NOT NULL, agent_id TEXT NOT NULL, source_id TEXT NOT NULL,
  doc_id TEXT NOT NULL, kind TEXT NOT NULL, at TEXT NOT NULL,
  PRIMARY KEY (session_id, agent_id, source_id, doc_id, kind));
"""


class SeenStore:
    """会話キーごとの返し済み・前回読んだ内容・閲覧と編集を SQLite に読み書きする。"""

    def __init__(self, path: Path, retention_days: int) -> None:
        self.path = path
        self.retention_days = retention_days

    def returned(
        self,
        key: SessionKey | None,
        source_id: str,
        kind: ReturnKind,
        versions: Mapping[str, str],
    ) -> set[str]:
        """同じバージョンをこの会話で返し済みの文書の ID を返す。"""
        raise NotImplementedError

    def mark_returned(
        self,
        key: SessionKey | None,
        source_id: str,
        kind: ReturnKind,
        documents: Sequence[Document],
    ) -> None:
        """返した文書のバージョンを記録し、本文なら内容と閲覧も記録する。"""
        raise NotImplementedError

    def last_read(self, key: SessionKey | None, source_id: str) -> dict[str, LastRead]:
        """この会話で最後に本文を返したときの内容を返す。"""
        raise NotImplementedError

    def record_activity(
        self,
        key: SessionKey | None,
        source_id: str,
        doc_ids: Sequence[str],
        kind: ActivityKind,
    ) -> None:
        """書いた文書を編集として記録する。"""
        raise NotImplementedError

    def activity(self, key: SessionKey | None, source_id: str) -> list[Activity]:
        """この会話で閲覧・編集した文書を返す。"""
        raise NotImplementedError

    def forget(self, key: SessionKey) -> int:
        """1 つの会話キーの記録を全て消す。"""
        raise NotImplementedError

    def purge_expired(self, *, now: datetime | None = None) -> int:
        """保持日数を過ぎた会話の記録を消す。"""
        raise NotImplementedError
