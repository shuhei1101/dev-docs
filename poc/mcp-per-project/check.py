"""server.py を起動した状態で、成功条件を HTTP の要求で確かめて結果を出す。"""

from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:8781"
PROTOCOL_VERSION = "2025-06-18"
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client: httpx.Client, path: str, method: str, params: dict, session: str | None = None, req_id: int | None = 1) -> tuple[int, dict | None, str | None]:
    """JSON-RPC を 1 回送り、ステータス・結果・セッション ID を返す。"""
    headers = dict(HEADERS)
    if session:
        headers["mcp-session-id"] = session
        headers["mcp-protocol-version"] = PROTOCOL_VERSION
    body: dict = {"jsonrpc": "2.0", "method": method, "params": params}
    if req_id is not None:
        body["id"] = req_id
    response = client.post(f"{BASE}{path}", headers=headers, json=body)
    payload = None
    # SSE で返る: data の行から JSON を取り出す
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):])
    elif response.content and response.headers.get("content-type", "").startswith("application/json"):
        payload = response.json()
    return response.status_code, payload, response.headers.get("mcp-session-id")


def initialize(client: httpx.Client, path: str) -> tuple[int, dict | None, str | None]:
    """initialize と initialized の通知を送り、セッションを開く。"""
    status, payload, session = rpc(client, path, "initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "poc-check", "version": "0"},
    })
    if session:
        rpc(client, path, "notifications/initialized", {}, session=session, req_id=None)
    return status, payload, session


def main() -> int:
    """成功条件を順に確かめる。"""
    results: list[tuple[str, bool, str]] = []
    with httpx.Client(timeout=10) as client:
        sessions: dict[str, str | None] = {}
        # 2 つの MCP が応答する
        infos = {}
        for name in ("alpha", "beta"):
            status, payload, session = initialize(client, f"/{name}/mcp")
            sessions[name] = session
            result = (payload or {}).get("result", {})
            infos[name] = (status, result.get("serverInfo", {}).get("name"), result.get("instructions"))
        ok = all(i[0] == 200 for i in infos.values()) and infos["alpha"][1:] != infos["beta"][1:]
        results.append(("2 つの MCP が応答する", ok, json.dumps(infos, ensure_ascii=False)))

        # ツールの説明文がプロジェクトごとに別
        descriptions = {}
        for name in ("alpha", "beta"):
            _, payload, _ = rpc(client, f"/{name}/mcp", "tools/list", {}, session=sessions[name], req_id=2)
            tools = (payload or {}).get("result", {}).get("tools", [])
            descriptions[name] = [(t["name"], t.get("description")) for t in tools]
        ok = descriptions["alpha"] != descriptions["beta"]
        results.append(("ツールの説明文が別", ok, json.dumps(descriptions, ensure_ascii=False)))

        # 呼び先が混ざらない
        _, payload, _ = rpc(client, "/alpha/mcp", "tools/call", {"name": "search", "arguments": {"query": "x"}}, session=sessions["alpha"], req_id=3)
        text = json.dumps((payload or {}).get("result", {}).get("content", []), ensure_ascii=False)
        results.append(("呼び先が混ざらない", "project=alpha " in text and "beta" not in text, text))

        # 起動した後に足せる（alpha のセッションが切れない）
        added = client.post(f"{BASE}/_poc/projects/gamma").json()
        status, payload, _ = initialize(client, "/gamma/mcp")
        result = (payload or {}).get("result", {})
        alpha_status, alpha_payload, _ = rpc(client, "/alpha/mcp", "ping", {}, session=sessions["alpha"], req_id=4)
        ok = status == 200 and result.get("serverInfo", {}).get("name") == "dev-docs-gamma" and "gamma" in (result.get("instructions") or "") and alpha_status == 200 and "result" in (alpha_payload or {})
        results.append(("起動した後に足せる", ok, f"running={added['running']} gamma={status} {result.get('serverInfo')} alpha_ping={alpha_status}"))

        # 起動した後に止められる
        removed = client.delete(f"{BASE}/_poc/projects/beta").json()
        status, _, _ = initialize(client, "/beta/mcp")
        ok = status == 404 and not any(k.startswith("beta") for k in removed["running"])
        results.append(("起動した後に止められる", ok, f"beta={status} running={removed['running']}"))

        # ref のパス
        status, payload, _ = initialize(client, "/alpha@feature-x/mcp")
        result = (payload or {}).get("result", {})
        running = client.get(f"{BASE}/_poc/projects").json()["running"]
        ok = status == 200 and result.get("serverInfo", {}).get("name") == "dev-docs-alpha@feature-x"
        results.append(("ref のパス", ok, f"status={status} {result.get('serverInfo')} running={running}"))

    for label, ok, detail in results:
        print(f"{'OK ' if ok else 'NG '} {label}: {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
