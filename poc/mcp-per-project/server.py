"""1 プロセス・1 ポートで、プロジェクトごとの MCP サーバーを /{name}/mcp・/{name}@{ref}/mcp に立てる PoC。"""

from __future__ import annotations

import contextlib
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

import anyio
from anyio.abc import TaskGroup
from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

MCP_PATH = re.compile(r"^/(?P<name>[a-z0-9-]+)(?:@(?P<ref>[^/]+))?/mcp/?$")
INITIAL_PROJECTS = ["alpha", "beta"]
NOT_FOUND = 404


@dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    """動いている 1 つの MCP サーバーの session manager と、止めるための cancel scope。"""

    manager: StreamableHTTPSessionManager
    cancel_scope: anyio.CancelScope
    stopped: anyio.Event


def project_key(name: str, ref: str | None) -> str:
    """プロジェクト名と ref から MCP サーバーのキーを作る。"""
    return f"{name}@{ref}" if ref else name


def build_server(key: str) -> MCPServer:
    """キーごとに instructions とツールの説明文を変えた MCP サーバーを作る。"""
    server = MCPServer(
        name=f"dev-docs-{key}",
        instructions=f"PROJECT={key}: {key} の開発ドキュメントを配信する MCP サーバー",
    )

    @server.tool(name="search", description=f"{key} の開発ドキュメントを検索する")
    def search(query: str) -> str:
        """呼び先が混ざらないかを見るため、キーをそのまま返すスタブ。"""
        return f"project={key} query={query}"

    # session manager は streamable_http_app() を呼んだときに作られる
    server.streamable_http_app(streamable_http_path="/mcp")
    return server


class Registry:
    """プロジェクトごとの session manager を、アプリ全体の task group の中で開始・停止する。"""

    def __init__(self, task_group: TaskGroup) -> None:
        self._task_group = task_group
        self._entries: dict[str, Entry] = {}
        self._projects: set[str] = set()
        self._lock = anyio.Lock()

    def keys(self) -> list[str]:
        """動いている MCP サーバーのキーを返す。"""
        return sorted(self._entries)

    async def add_project(self, name: str) -> None:
        """プロジェクトを配信の対象に加え、MCP サーバーを開始する。"""
        self._projects.add(name)
        await self._start(project_key(name, None))

    async def remove_project(self, name: str) -> None:
        """プロジェクトを配信の対象から外し、ref つきを含む MCP サーバーを全て止める。"""
        self._projects.discard(name)
        for key in [k for k in self._entries if k == name or k.startswith(f"{name}@")]:
            entry = self._entries.pop(key)
            entry.cancel_scope.cancel()
            await entry.stopped.wait()

    async def resolve(self, name: str, ref: str | None) -> StreamableHTTPSessionManager | None:
        """要求のパスに当たる session manager を返す。ref つきは最初の要求で開始する。"""
        # 配信の対象でないプロジェクト: 呼び出し側が 404 を返す
        if name not in self._projects:
            return None
        key = project_key(name, ref)
        await self._start(key)
        return self._entries[key].manager

    async def _start(self, key: str) -> None:
        """MCP サーバーを開始し、session manager の run() に入るまで待つ。"""
        async with self._lock:
            # 既に動いている: 何もしない
            if key in self._entries:
                return
            manager = build_server(key).session_manager
            cancel_scope = anyio.CancelScope()
            stopped = anyio.Event()
            started = anyio.Event()

            async def run() -> None:
                try:
                    with cancel_scope:
                        async with manager.run():
                            started.set()
                            await anyio.sleep_forever()
                finally:
                    stopped.set()

            self._task_group.start_soon(run)
            await started.wait()
            self._entries[key] = Entry(manager=manager, cancel_scope=cancel_scope, stopped=stopped)


class App:
    """MCP のパスを session manager へ振り分け、それ以外を PoC 用の管理のルートへ回す ASGI アプリ。"""

    def __init__(self, initial: list[str]) -> None:
        self._registry: Registry | None = None
        self._initial = initial
        self._admin = Starlette(
            routes=[
                Route("/_poc/projects", self._list, methods=["GET"]),
                Route("/_poc/projects/{name}", self._add, methods=["POST"]),
                Route("/_poc/projects/{name}", self._remove, methods=["DELETE"]),
            ]
        )

    @property
    def registry(self) -> Registry:
        """起動後の Registry を返す。"""
        if self._registry is None:
            raise RuntimeError("起動前に要求を受けました")
        return self._registry

    @contextlib.asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """アプリ全体の task group を開き、初期のプロジェクトの MCP サーバーを開始する。"""
        async with anyio.create_task_group() as task_group:
            self._registry = Registry(task_group)
            for name in self._initial:
                await self._registry.add_project(name)
            yield
            task_group.cancel_scope.cancel()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """要求の種類とパスで振り分ける。"""
        # 起動・終了の通知: lifespan で task group を開閉する
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        match = MCP_PATH.match(scope["path"])
        # MCP のパスでない: PoC 用の管理のルートへ回す
        if match is None:
            await self._admin(scope, receive, send)
            return
        manager = await self.registry.resolve(match["name"], match["ref"])
        # 配信の対象でないプロジェクト: 404
        if manager is None:
            await PlainTextResponse("not found", status_code=NOT_FOUND)(scope, receive, send)
            return
        await manager.handle_request(scope, receive, send)

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        async with self.lifespan():
            await receive()
            await send({"type": "lifespan.startup.complete"})
            await receive()
        await send({"type": "lifespan.shutdown.complete"})

    async def _list(self, request: Request) -> JSONResponse:
        return JSONResponse({"running": self.registry.keys()})

    async def _add(self, request: Request) -> JSONResponse:
        await self.registry.add_project(request.path_params["name"])
        return JSONResponse({"running": self.registry.keys()})

    async def _remove(self, request: Request) -> JSONResponse:
        await self.registry.remove_project(request.path_params["name"])
        return JSONResponse({"running": self.registry.keys()})


app = App(INITIAL_PROJECTS)
