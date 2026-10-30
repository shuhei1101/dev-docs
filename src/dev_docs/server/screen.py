"""画面（React の SPA）のビルドを返す。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from dev_docs.shared.errors import ScreenBuildMissingError

SCREEN_DIST_DIR = Path(__file__).parent.parent / "screen"
EXCLUDED_PREFIXES = ("_api", "mcp", "_admin")
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

    return router
