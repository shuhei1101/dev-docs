"""dev-docs serve を別のポートで起動し、起動直後と status の応答時間を測る。"""
import json, os, socket, subprocess, sys, threading, time
import httpx

worktree, label, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
state = f"/tmp/pr136/measure/state-{label}"
env = {**os.environ, "DEV_DOCS_PORT": str(port), "DEV_DOCS_STATE_DIR": state}
H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
KNOWLEDGE = "/mnt/c/Users/shuhe/repo/knowledge/.claude/worktrees/develop"
t0 = time.monotonic()
log = open(f"/tmp/pr136/measure/serve-{label}.log", "w")
proc = subprocess.Popen(["uv", "run", "dev-docs", "serve"], cwd=worktree, env=env, stdout=log, stderr=subprocess.STDOUT)

def el(): return round(time.monotonic() - t0, 2)
def say(msg): print(f"[{el():7.2f}s] {msg}", flush=True)

def call(path, name, args, timeout):
    start = time.monotonic()
    try:
        r = httpx.post(f"http://127.0.0.1:{port}{path}", headers=H, timeout=timeout,
                       json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
        result = r.json()["result"]
        text = "".join(p["text"] for p in result["content"] if p["type"] == "text")
        return round(time.monotonic() - start, 2), result, text
    except Exception as e:
        return round(time.monotonic() - start, 2), None, f"{type(e).__name__}"

try:
    while True:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close(); break
        except OSError:
            time.sleep(0.2)
    say("待ち受けを始めた")
    out = {}
    def search():
        out["search"] = call("/mcp/", "search_docs", {"cwd": KNOWLEDGE, "source": "knowledge", "view": "count"}, 600)
        say(f"search_docs(source: knowledge) の応答: {out['search'][0]} 秒（{out['search'][2][:60]!r}）")
    th = threading.Thread(target=search); th.start()
    sec, res, text = call("/_admin/mcp/", "status", {"format": "json"}, 600)
    data = (res or {}).get("structuredContent") or {}
    say(f"起動直後の status の応答: {sec} 秒（loading: {data.get('loading')}）")
    while True:
        sec, res, text = call("/_admin/mcp/", "status", {"format": "json"}, 600)
        data = (res or {}).get("structuredContent") or {}
        if data.get("loading") is False:
            break
        time.sleep(1)
    say(f"status が loading: false を返した（その要求の応答 {sec} 秒）")
    th.join()
    for i in range(3):
        sec, res, text = call("/_admin/mcp/", "status", {"format": "json"}, 600)
        data = (res or {}).get("structuredContent") or {}
        pending = sum(1 for s in data.get("sources", []) if s.get("status") == "serving" and s.get("sync") is None)
        say(f"読み込みの後の status の応答 {i+1} 回目: {sec} 秒（同期の件数が無い配信中の配信元: {pending}）")
        time.sleep(2)
    # 検査が全て済むまで待ち、済んだ後の応答を測る
    while True:
        sec, res, text = call("/_admin/mcp/", "status", {"format": "json"}, 600)
        data = (res or {}).get("structuredContent") or {}
        pending = sum(1 for s in data.get("sources", []) if s.get("status") == "serving" and s.get("sync") is None)
        if pending == 0:
            break
        time.sleep(5)
    say(f"検査が全て済んだ（その要求の応答 {sec} 秒）")
    for i in range(3):
        sec, res, text = call("/_admin/mcp/", "status", {"format": "json"}, 600)
        say(f"検査の後の status の応答 {i+1} 回目: {sec} 秒")
finally:
    proc.terminate()
    try: proc.wait(timeout=30)
    except subprocess.TimeoutExpired: proc.kill()
