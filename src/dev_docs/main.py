"""`dev-docs serve` の処理と部品の配線。"""

from __future__ import annotations

import argparse
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dev_docs.features.settings.types import TerminalConfig
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import SourceStatus

EXIT_CONFIG_INVALID = 2
EXIT_PORT_IN_USE = 3


class PortInUseError(OSError):
    """待ち受けのアドレスとポートで待ち受けられないことを表す。"""

    def __init__(self, bind: str, port: int) -> None:
        super().__init__(f"{bind}:{port} は使用中です")
        self.bind = bind
        self.port = port


@dataclass(frozen=True)
class Handlers:
    """入口（画面・MCP）が使う部品を 1 回だけ作って束ねたもの。"""

    terminal: TerminalConfig
    registry: SourceRegistry
    store: Any
    snapshots: Any
    converter: Any
    seen: Any
    locks: Any
    settings_lock: threading.Lock
    templates: Any
    checker: Any
    columns: Any
    reload_sources: Callable[[TerminalConfig], list[SourceStatus]]


def run_serve(args: argparse.Namespace) -> int:
    """端末の設定を読み、配信元を配線して待ち受け、停止の合図まで動く。"""
    raise NotImplementedError


def check_port(bind: str, port: int) -> None:
    """待ち受けのアドレスとポートで待ち受けられるかを、一度 bind して確かめる。"""
    raise NotImplementedError


def build_handlers(terminal: TerminalConfig) -> Handlers:
    """端末の設定から部品を 1 回だけ作り、配信元を読んで配線済みの関数にする。"""
    raise NotImplementedError


def reload_sources(
    terminal: TerminalConfig,
    *,
    registry: SourceRegistry,
    store: Any,
    checker: Any,
    converter: Any,
) -> list[SourceStatus]:
    """配信元の一覧を読み直し、配信元の内容を控えた部品の控えを捨てる。"""
    raise NotImplementedError
