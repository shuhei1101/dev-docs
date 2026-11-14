"""`dev-docs serve`・`dev-docs migrate` の処理と部品の配線。"""

from __future__ import annotations

import argparse
import asyncio
import errno
import logging
import os
import socket
import sys
import threading
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dev_docs.features.convert.service import ConvertService
from dev_docs.features.lifecycle.control import RestartControl
from dev_docs.features.lifecycle.types import SERVE_ARGV, SHUTDOWN_WAIT_FACTOR
from dev_docs.features.prompt_doc.runtime import PromptSet, load_prompts, prompts_dir
from dev_docs.features.prompt_doc.types import PromptInvalidError
from dev_docs.features.settings.query import config_path, listen_port, load_terminal_config
from dev_docs.features.settings.types import TerminalConfig, TerminalConfigInvalidError
from dev_docs.features.view.columns import COLUMNS_DIR, ColumnSettings
from dev_docs.integrations.project_index.client import (
    PROJECT_INDEX_TIMEOUT_SEC,
    ProjectIndexClient,
)
from dev_docs.integrations.project_index.types import SettingsSourcesView
from dev_docs.server.mcp.result import mcp_prompt_ids
from dev_docs.shared.errors import ProjectIndexUnreachableError

if TYPE_CHECKING:
    from dev_docs.features.migrate.types import SourcesPort

EXIT_CONFIG_INVALID = 2
EXIT_PORT_IN_USE = 3
EXIT_PROMPT_INVALID = 4
LOG_FILE = "dev-docs.log"
LOG_MAX_BYTES = 5_000_000
LOG_BACKUPS = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
BIND_ERRORS = (errno.EADDRINUSE, errno.EACCES)
PROJECT_INDEX_PORT_ENV = "PROJECT_INDEX_PORT"
PROJECT_INDEX_PORT_DEFAULT = "8786"
START_GUIDE = "project-index を起動してから、再読み込みしてください。"

logger = logging.getLogger(__name__)


class PortInUseError(OSError):
    """待ち受けのアドレスとポートで待ち受けられないことを表す。"""

    def __init__(self, bind: str, port: int) -> None:
        super().__init__(f"{bind}:{port} は使用中です")
        self.bind = bind
        self.port = port


@dataclass(frozen=True)
class Handlers:
    """入口（画面・MCP）が使用する部品を 1 回だけ作ってまとめたもの。"""

    terminal: TerminalConfig
    project_index: ProjectIndexClient
    converter: ConvertService
    columns: ColumnSettings
    restart: RestartControl
    prompts: PromptSet


def _setup_logging(log_dir: Path) -> list[logging.Handler]:
    """ログを標準エラーと `{log_dir}/dev-docs.log` に書き込む設定にし、追加したハンドラを返却する。"""
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
    """追加したログのハンドラを除去して閉じる。"""
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
    """端末の設定を読み込み、部品を配線して待ち受け、停止の合図まで動く。"""
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
        try:
            handlers = build_handlers(terminal)
        except PromptInvalidError as error:
            for problem in error.problems:
                print(problem.line(), file=sys.stderr, flush=True)
            return EXIT_PROMPT_INVALID
        app = build_app(handlers)
        print(f"http://{terminal.bind}:{port}/", flush=True)
        if terminal.leftover_sources:
            logger.warning(
                "端末の設定に前のバージョンの sources が残っている（%s）。project-index の端末の設定へ追加してください",
                "・".join(terminal.leftover_sources),
            )
        announce_sources(terminal)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=terminal.bind,
                port=port,
                log_config=None,
                # 処理中の要求を待つ上限（project-index の応答を待つ要求が一番長い）
                timeout_graceful_shutdown=int(PROJECT_INDEX_TIMEOUT_SEC * SHUTDOWN_WAIT_FACTOR),
            )
        )
        handlers.restart.attach(server)
        server.run()
        if not server.started:
            # 確認した後に他のプロセスがポートを取った
            _report_port(terminal.bind, port)
            return EXIT_PORT_IN_USE
        # 再起動を要求されて止まったときは、同じプロセスを `serve` で置き換える
        if handlers.restart.requested:
            _close_logging(log_handlers)
            os.execv(sys.executable, [sys.executable, *SERVE_ARGV])
        return 0
    finally:
        _close_logging(log_handlers)


def announce_sources(terminal: TerminalConfig) -> threading.Thread:
    """待ち受けの後に project-index の配信元の状態を問い合わせ、配信中の配信元か、つながらないことを通知する。"""

    async def ask() -> None:
        client = ProjectIndexClient(terminal.project_index, timeout=PROJECT_INDEX_TIMEOUT_SEC)
        try:
            for state in await client.list_sources():
                if state.status == "serving":
                    print(state.id, flush=True)
        finally:
            await client.aclose()

    def work() -> None:
        try:
            asyncio.run(ask())
        except ProjectIndexUnreachableError as error:
            print(f"{error.message}\n{START_GUIDE}", file=sys.stderr, flush=True)
            logger.error(  # noqa: TRY400 つながらないことだけを記録し、スタックトレースは要らない
                "project-index につながらない（%s・%s）", error.address, error.reason
            )
        except Exception:
            logger.exception("配信元の通知に失敗した")

    thread = threading.Thread(target=work, name="dev-docs-announce", daemon=True)
    thread.start()
    return thread


def check_port(bind: str, port: int) -> None:
    """待ち受けのアドレスとポートで待ち受けられるかを、一度 bind して確認する。"""
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
    """端末の設定から部品を 1 回だけ作り、配線済みの関数にする（project-index にはまだ問い合わせない）。"""
    # プロンプトの YAML が違反するときは、state_dir を作る前に止める
    prompts = load_prompts(prompts_dir(os.environ), required=mcp_prompt_ids())
    state_dir = terminal.state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    return Handlers(
        terminal=terminal,
        project_index=ProjectIndexClient(terminal.project_index, timeout=PROJECT_INDEX_TIMEOUT_SEC),
        converter=ConvertService(),
        columns=ColumnSettings(state_dir / COLUMNS_DIR),
        restart=RestartControl(),
        prompts=prompts,
    )


def _project_index_address(given: str | None, env: Mapping[str, str]) -> str:
    """`--project-index`、無ければ `PROJECT_INDEX_PORT`（無ければ 8786）から接続先を決める。"""
    if given:
        return given
    port = env.get(PROJECT_INDEX_PORT_ENV) or PROJECT_INDEX_PORT_DEFAULT
    return f"http://127.0.0.1:{port}"


def _sources_port(address: str) -> SourcesPort:
    """取得・保存を呼ぶたびに 1 回の `asyncio.run` で project-index の呼び出しを作って閉じる API を返却する。"""
    # 移し替えの型は起動の定数を参照するため、呼ぶときに読み込む
    from dev_docs.features.migrate.types import SourcesPort

    def fetch() -> SettingsSourcesView:
        async def run() -> SettingsSourcesView:
            client = ProjectIndexClient(address, timeout=PROJECT_INDEX_TIMEOUT_SEC)
            try:
                return await client.settings_sources()
            finally:
                await client.aclose()

        return asyncio.run(run())

    def save(rows: list[dict[str, Any]], expected_version: str | None) -> None:
        async def run() -> None:
            client = ProjectIndexClient(address, timeout=PROJECT_INDEX_TIMEOUT_SEC)
            try:
                await client.save_settings_sources(rows, expected_version=expected_version)
            finally:
                await client.aclose()

        asyncio.run(run())

    return SourcesPort(fetch=fetch, save=save)


def run_migrate(args: argparse.Namespace) -> int:
    """`dev-docs migrate` の解析結果で対象を決め、適用する手順を表示するか適用する。"""
    from dev_docs.features.migrate.service import apply_migration, plan_migration, resolve_target
    from dev_docs.features.migrate.types import MigrationError

    address = _project_index_address(args.project_index, os.environ)
    try:
        target = resolve_target(env=os.environ)
        data, steps = plan_migration(target)
        # 手順を表示するだけで、書き換えない
        if args.plan:
            for step in steps:
                suffix = " [destructive]" if step.destructive else ""
                print(f"{step.version}: {step.description}{suffix}")
            return 0
        # `--record` は手順を当てず、バージョンだけを書き換える
        if args.record:
            outcome = apply_migration(
                target,
                data,
                [],
                allow_destructive=False,
                sources_port=None,
                project_index=address,
                now=datetime.now(UTC),
            )
            print(
                f"{target.file} の version を {target.current} にしました（バックアップ: {outcome.backup}）"
            )
            return 0
        if not steps:
            print(f"移し替えは要りません（version {target.current}）")
            return 0
        exports = any(step.op == "export_sources" for step in steps)
        outcome = apply_migration(
            target,
            data,
            steps,
            allow_destructive=args.allow_destructive,
            sources_port=_sources_port(address) if exports else None,
            project_index=address,
            now=datetime.now(UTC),
        )
        print(
            f"{target.file} を version {target.current} に移し替えました（バックアップ: {outcome.backup}）"
        )
        for kept in outcome.kept:
            print(f"{kept}: project-index に同じ id の別の行があるため移しませんでした")
        for config in outcome.unresolved:
            print(f"{config}: 配信元の ID を求められないため移しませんでした")
        return 0
    except MigrationError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
