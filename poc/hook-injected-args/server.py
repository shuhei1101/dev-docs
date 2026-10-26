"""受け取った引数をそのまま args.jsonl に書く PoC の MCP サーバー（Streamable HTTP）。

Usage:
# 127.0.0.1:{ポート} で待ち受け、{ログのフォルダ} に args.jsonl と tools.json を書く
uv run python server.py --port {ポート} --log-dir {ログのフォルダ}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

HOST = "127.0.0.1"


class Condition(BaseModel):
    """1 つの項目を比べる条件。"""

    field: str = Field(description="比べる項目の名前")
    op: Literal["eq", "ne"] = Field(description="比べ方")
    value: str = Field(description="比べる値")


class Group(BaseModel):
    """条件と群を and / or で束ねる群。"""

    op: Literal["and", "or"] = Field(description="束ね方")
    items: list[Group | Condition] = Field(description="束ねる条件と群")


def build_server(log_dir: Path) -> MCPServer:
    """probe と probe_delete を持つ MCP サーバーを作る。"""
    server = MCPServer(name="pocdocs")
    args_log = log_dir / "args.jsonl"

    def record(tool: str, filter: Group, cwd: str | None, session_id: str | None, agent_id: str | None) -> str:
        """受け取った引数を 1 行の JSON で書き足し、そのまま返す。"""
        line = {
            "tool": tool,
            "filter": filter.model_dump(mode="json"),
            "cwd": cwd,
            "session_id": session_id,
            "agent_id": agent_id,
        }
        with args_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return json.dumps(line, ensure_ascii=False)

    @server.tool(name="probe", description="受け取った引数をそのまま返す（読み取り）", annotations=ToolAnnotations(read_only_hint=True))
    def probe(filter: Group, cwd: str | None = None, session_id: str | None = None, agent_id: str | None = None) -> str:
        """読み取りのツールとして引数を記録する。"""
        return record("probe", filter, cwd, session_id, agent_id)

    @server.tool(name="probe_delete", description="受け取った引数をそのまま返す（削除）", annotations=ToolAnnotations(destructive_hint=True))
    def probe_delete(filter: Group, cwd: str | None = None, session_id: str | None = None, agent_id: str | None = None) -> str:
        """削除のツールとして引数を記録する。"""
        return record("probe_delete", filter, cwd, session_id, agent_id)

    return server


def main() -> int:
    """入力スキーマを tools.json に書き出してから待ち受ける。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    server = build_server(args.log_dir)

    # Claude Code に渡る入力スキーマ（$ref の再帰）を残す
    tools = asyncio.run(server.list_tools())
    schemas = {tool.name: tool.input_schema for tool in tools}
    (args.log_dir / "tools.json").write_text(json.dumps(schemas, ensure_ascii=False, indent=2), encoding="utf-8")

    uvicorn.run(server.streamable_http_app(), host=HOST, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
