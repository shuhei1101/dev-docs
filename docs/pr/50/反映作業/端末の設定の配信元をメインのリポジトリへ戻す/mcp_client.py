"""反映作業のスクリプトが共有する、対象のパス・default_ref の設定の確かめ・dev-docs の MCP の呼び出し。"""

import json
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

SETTINGS = Path.home() / ".config/dev-docs/settings.yaml"
BACKUP = Path.home() / ".config/dev-docs/settings.yaml.pr50.bak"
# (今の config, 書き換え先の config)
REPLACEMENTS = [
    (
        "/mnt/c/Users/shuhe/repo/shuhdev-gateway/.claude/worktrees/develop/dev-docs.yaml",
        "/mnt/c/Users/shuhe/repo/shuhdev-gateway/dev-docs.yaml",
    ),
    (
        "/mnt/c/Users/shuhe/repo/claude-balancer/.claude/worktrees/develop/dev-docs.yaml",
        "/mnt/c/Users/shuhe/repo/claude-balancer/dev-docs.yaml",
    ),
    (
        "/mnt/c/Users/shuhe/repo/alias-inject/.claude/worktrees/develop/dev-docs.yaml",
        "/mnt/c/Users/shuhe/repo/alias-inject/dev-docs.yaml",
    ),
    (
        "/mnt/c/Users/shuhe/repo/rule-inject/.claude/worktrees/develop/dev-docs.yaml",
        "/mnt/c/Users/shuhe/repo/rule-inject/dev-docs.yaml",
    ),
]
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
DOCS_MCP_URL = "http://127.0.0.1:8781/mcp/"
TIMEOUT_SEC = 120
PROTOCOL_VERSION = "2025-06-18"
DEFAULT_REF = "develop"
DEFAULT_REF_LINE = re.compile(r"^default_ref:\s*['\"]?([^'\"\s#]+)", re.MULTILINE)


def config_at_default_ref(config: str) -> bool:
    """サーバーと同じく、ディスクの設定の `default_ref`（無ければ develop）の commit に設定があるか。"""
    path = Path(config)
    default_ref = DEFAULT_REF
    # ディスクに設定があれば、その default_ref を使う
    if path.is_file():
        match = DEFAULT_REF_LINE.search(path.read_text(encoding="utf-8"))
        if match:
            default_ref = match.group(1)
    result = subprocess.run(
        ["git", "-C", str(path.parent), "cat-file", "-e", f"{default_ref}:{path.name}"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _post(
    url: str, body: dict[str, Any], session_id: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    """JSON-RPC を 1 回送り、応答の JSON とセッション ID を返す。"""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if session_id:
        headers["mcp-session-id"] = session_id
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
        new_session_id = response.headers.get("mcp-session-id") or session_id
        content_type = response.headers.get("Content-Type") or ""
        text = response.read().decode()
    # SSE で返ったときは最後の data 行を応答の JSON とする
    if "text/event-stream" in content_type:
        data_lines = [
            line[len("data:") :].strip() for line in text.splitlines() if line.startswith("data:")
        ]
        text = data_lines[-1] if data_lines else ""
    return (json.loads(text) if text.strip() else None), new_session_id


def initialize(url: str) -> str | None:
    """initialize と initialized の通知を送り、セッション ID を返す。"""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "pr50-reflection", "version": "0"},
        },
    }
    _, session_id = _post(url, body, None)
    _post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id)
    return session_id


def call_tool(url: str, name: str, arguments: dict[str, Any]) -> str:
    """MCP のツールを呼び、結果の text を連結して返す。エラーの結果は RuntimeError にする。"""
    session_id = initialize(url)
    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    payload, _ = _post(url, body, session_id)
    if payload is None or "error" in payload:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    result = payload["result"]
    text = "\n".join(item.get("text", "") for item in result.get("content", []))
    if result.get("isError"):
        raise RuntimeError(text)
    return text
