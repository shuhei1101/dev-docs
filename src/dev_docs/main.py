"""`dev-docs serve` の処理と部品の配線。"""

from __future__ import annotations

import argparse
import errno
import logging
import os
import socket
import sys
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from dev_docs.features.documents.store import check_sync
from dev_docs.features.lifecycle.control import RestartControl
from dev_docs.features.lifecycle.types import SERVE_ARGV, SHUTDOWN_WAIT_FACTOR
from dev_docs.features.settings.query import config_path, listen_port, load_terminal_config
from dev_docs.features.settings.types import TerminalConfig, TerminalConfigInvalidError
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import SourceStatus

EXIT_CONFIG_INVALID = 2
EXIT_PORT_IN_USE = 3
LOG_FILE = "dev-docs.log"
LOG_MAX_BYTES = 5_000_000
LOG_BACKUPS = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
BIND_ERRORS = (errno.EADDRINUSE, errno.EACCES)

logger = logging.getLogger(__name__)


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
    checker: Any
    columns: Any
    reload_sources: Callable[[TerminalConfig], list[SourceStatus]]
    restart: RestartControl


def _setup_logging(log_dir: Path) -> list[logging.Handler]:
    """ログを標準エラーと `{log_dir}/dev-docs.log` に書く設定にし、足したハンドラを返す。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stderr),
        RotatingFileHandler(
            log_dir / LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
        ),
    ]
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)
    return handlers


def _close_logging(log_handlers: list[logging.Handler]) -> None:
    """足したログのハンドラを外して閉じる。"""
    root = logging.getLogger()
    for handler in log_handlers:
        root.removeHandler(handler)
        handler.close()


def _report_invalid(error: TerminalConfigInvalidError) -> None:
    """端末の設定の違反を、標準エラーに 1 行ずつ出す。"""
    if error.violations:
        for violation in error.violations:
            print(f"{error.file}: {violation.path}: {violation.rule}", file=sys.stderr)
    else:
        print(error.message, file=sys.stderr)


def _report_port(bind: str, port: int) -> None:
    """ポートが使用中のことを標準エラーに出す。"""
    print(f"{bind}:{port} は使用中です。DEV_DOCS_PORT で別のポートを指定できます", file=sys.stderr)


def run_serve(args: argparse.Namespace) -> int:
    """端末の設定を読み、配信元を配線して待ち受け、停止の合図まで動く。"""
    import uvicorn

    from dev_docs.server.app import build_app

    try:
        terminal = load_terminal_config(config_path(os.environ))
        port = listen_port(terminal, os.environ)
    except TerminalConfigInvalidError as error:
        _report_invalid(error)
        return EXIT_CONFIG_INVALID
    log_handlers = _setup_logging(terminal.log_dir)
    try:
        try:
            check_port(terminal.bind, port)
        except PortInUseError:
            _report_port(terminal.bind, port)
            return EXIT_PORT_IN_USE
        handlers = build_handlers(terminal)
        app = build_app(handlers)
        print(f"http://{terminal.bind}:{port}/", flush=True)
        for source in handlers.registry.served():
            print(source.id, flush=True)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=terminal.bind,
                port=port,
                log_config=None,
                # 処理中の要求を待つ上限（スクリプトの実行が一番長い要求になる）
                timeout_graceful_shutdown=int(terminal.script_timeout_sec * SHUTDOWN_WAIT_FACTOR),
            )
        )
        handlers.restart.attach(server)
        server.run()
        if not server.started:
            # 確かめた後に他のプロセスがポートを取った
            _report_port(terminal.bind, port)
            return EXIT_PORT_IN_USE
        # 再起動を要求されて止まったときは、同じプロセスを `serve` で置き換える
        if handlers.restart.requested:
            _close_logging(log_handlers)
            os.execv(sys.executable, [sys.executable, *SERVE_ARGV])
        return 0
    finally:
        _close_logging(log_handlers)


def check_port(bind: str, port: int) -> None:
    """待ち受けのアドレスとポートで待ち受けられるかを、一度 bind して確かめる。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        # uvicorn と同じく SO_REUSEADDR を付け、閉じたばかりの接続が残るポートは使用中にしない
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind, port))
        except OSError as error:
            if error.errno in BIND_ERRORS:
                raise PortInUseError(bind, port) from error
            raise


def build_handlers(terminal: TerminalConfig) -> Handlers:
    """端末の設定から部品を 1 回だけ作り、配信元を読んで配線済みの関数にする。"""
    from dev_docs.features.convert.service import ConvertService
    from dev_docs.features.documents.store import DocumentStore
    from dev_docs.features.history.snapshot import SnapshotStore
    from dev_docs.features.seen.store import SeenStore
    from dev_docs.features.validation.service import DocumentChecker
    from dev_docs.features.view.columns import COLUMNS_DIR, ColumnSettings
    from dev_docs.features.write.locks import SourceLocks

    state_dir = terminal.state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    registry = SourceRegistry()
    snapshots = SnapshotStore(state_dir / "snapshots")
    store = DocumentStore(snapshots)
    converter = ConvertService(state_dir / "converted", store, terminal.script_timeout_sec)
    seen = SeenStore(state_dir / "seen.sqlite3", terminal.seen_retention_days)
    checker = DocumentChecker(store, terminal.script_timeout_sec)
    columns = ColumnSettings(state_dir / COLUMNS_DIR)

    def reload(new_terminal: TerminalConfig) -> list[SourceStatus]:
        statuses = reload_sources(
            new_terminal, registry=registry, store=store, checker=checker, converter=converter
        )
        # 設定画面が起動時の一覧ではなく保存した一覧を見せるよう、起動時の端末の設定の一覧を差し替える
        terminal.sources[:] = new_terminal.sources
        return statuses

    reload(terminal)
    return Handlers(
        terminal=terminal,
        registry=registry,
        store=store,
        snapshots=snapshots,
        converter=converter,
        seen=seen,
        locks=SourceLocks(),
        settings_lock=threading.Lock(),
        checker=checker,
        columns=columns,
        reload_sources=reload,
        restart=RestartControl(),
    )


def reload_sources(
    terminal: TerminalConfig,
    *,
    registry: SourceRegistry,
    store: Any,
    checker: Any,
    converter: Any,
) -> list[SourceStatus]:
    """配信元の一覧を読み直し、配信元の内容を控えた部品の控えを捨てる。"""
    statuses = registry.reload(terminal)
    store.clear()
    checker.clear()
    converter.clear()
    for source in registry.served():
        report = check_sync(store, source)
        for label, values in (
            ("metadata の列の欠け", report.missing_refs),
            ("管理用の YAML に無いファイル", report.unindexed_files),
            ("ファイルが無い行", report.missing_body_files),
        ):
            if values:
                logger.warning(
                    "%s: %s %d 件: %s", report.source_id, label, len(values), "、".join(values)
                )
    return statuses


def run_migrate(args: argparse.Namespace) -> int:
    """`dev-docs migrate` の解析結果で対象を決め、当てる手順を表示するか当てる。"""
    from dev_docs.features.migrate.service import apply_migration, plan_migration, resolve_target
    from dev_docs.features.migrate.types import MigrationError

    try:
        target = resolve_target(args.source, env=os.environ)
        data, steps = plan_migration(target)
        # 手順を表示するだけで、書き換えない
        if args.plan:
            for step in steps:
                suffix = " [destructive]" if step.destructive else ""
                print(f"{step.version}: {step.description}{suffix}")
            return 0
        # `--record` は手順を当てず、バージョンだけを書き換える
        if args.record:
            backup = apply_migration(
                target, data, [], allow_destructive=False, now=datetime.now(UTC)
            )
            print(
                f"{target.file} の version を {target.current} にしました（バックアップ: {backup}）"
            )
            return 0
        if not steps:
            print(f"移し替えは要りません（version {target.current}）")
            return 0
        backup = apply_migration(
            target,
            data,
            steps,
            allow_destructive=args.allow_destructive,
            now=datetime.now(UTC),
        )
        print(
            f"{target.file} を version {target.current} に移し替えました（バックアップ: {backup}）"
        )
        return 0
    except MigrationError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
