"""設定画面からの端末の設定の保存。"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources.types import SourceStatus


def save_sources(
    sources: Sequence[SourceEntry],
    *,
    path: Path,
    reload: Callable[[TerminalConfig], list[SourceStatus]],
    lock: threading.Lock,
) -> list[SourceStatus]:
    """`settings.yaml` の `sources` だけを書き換え、検証に通ったら書いて配信元を読み直す。"""
    raise NotImplementedError
