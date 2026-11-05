"""画面（React の SPA）のビルドを返す。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.routing import BaseRoute, Match
from starlette.types import Scope

from dev_docs.shared.errors import ScreenBuildMissingError

SCREEN_DIST_DIR = Path(__file__).parent.parent / "screen"
EXCLUDED_PREFIXES = ("_api", "mcp", "_admin")
NON_GET_METHODS = ("POST", "PUT", "PATCH", "DELETE")
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
ASSETS_PREFIX = "assets/"


def build_screen_router(dist_dir: Path) -> APIRouter:
    """画面のビルド（`index.html` と `assets/`）を返すルーターを作る。"""
    router = APIRouter()

    @router.get("/{path:path}", include_in_schema=False)
    def screen(path: str) -> FileResponse:
        # API・MCP の誤ったパスには画面を返さない
        if path.split("/", 1)[0] in EXCLUDED_PREFIXES:
            raise HTTPException(status_code=404)
        if path.startswith(ASSETS_PREFIX):
            root = dist_dir.resolve()
            file = (root / path).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                raise HTTPException(status_code=404)
            return FileResponse(file, headers={"Cache-Control": IMMUTABLE_CACHE})
        index = dist_dir / "index.html"
        if not index.is_file():
            raise ScreenBuildMissingError(
                message=f"画面のビルドがありません（{index}）",
                next_steps=[
                    "frontend/ で画面をビルドする（vite build。出力先は src/dev_docs/screen/）"
                ],
            )
        return FileResponse(index, media_type="text/html", headers={"Cache-Control": NO_CACHE})

    @router.api_route("/{path:path}", methods=list(NON_GET_METHODS), include_in_schema=False)
    def reject(path: str, request: Request) -> None:
        # API・MCP・管理の頭のパス: 他のルートに無いメソッドなら 405、パス自体が無ければ 404
        if path.split("/", 1)[0] in EXCLUDED_PREFIXES:
            allowed = _allowed_methods(request.app.router.routes, request.scope, router)
            if allowed:
                raise HTTPException(status_code=405, headers={"Allow": ", ".join(allowed)})
            raise HTTPException(status_code=404)
        # 画面のパス: 画面の配信は GET だけを受ける
        raise HTTPException(status_code=405, headers={"Allow": "GET"})

    return router


def _allowed_methods(routes: Sequence[BaseRoute], scope: Scope, own: APIRouter) -> list[str]:
    """画面の配信のルーターを除くルートのうち、パスに当たりメソッドが合わないルートのメソッドを返す。"""
    allowed: list[str] = []
    for route in routes:
        # 画面の配信のルーター自身（GET の全てのパスに当たる）は照合しない
        included = getattr(route, "original_router", None)
        if included is own or route in own.routes:
            continue
        # 取り込んだルーター: 当たった子のメソッドを返さないため、中のルートを照合する
        if isinstance(included, APIRouter):
            allowed.extend(_allowed_methods(included.routes, scope, own))
            continue
        match, _ = route.matches(scope)
        if match == Match.PARTIAL:
            allowed.extend(sorted(getattr(route, "methods", None) or ()))
    return list(dict.fromkeys(allowed))
