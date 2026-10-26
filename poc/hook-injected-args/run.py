"""PoC のサーバーを立て、claude -p で各ケースを流し、成功条件を確かめて結果を出す。

Usage:
# results/ にログ（args.jsonl・hook.jsonl・tools.json・claude-*.json・run.log）を書く
uv run python run.py --out results
# Bash の cd を毎回起動フォルダへ戻す環境変数を立てて流す
uv run python run.py --out results-maintain --maintain-project-dir
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = "mcp__plugin_pocdocs_docs__probe"
PROBE_DELETE = "mcp__plugin_pocdocs_docs__probe_delete"
CLAUDE_TIMEOUT_SEC = 600
SERVER_START_TIMEOUT_SEC = 30
POLL_INTERVAL_SEC = 0.2
MAINTAIN_ENV = "CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"


@dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """claude -p を 1 回流すケース。"""

    name: str
    cwd: Path
    prompt: str
    allowed: tuple[str, ...]
    expected_cwd: Path | None


def free_port() -> int:
    """空いているポートを 1 つ返す。"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def filter_for(marker: str) -> dict:
    """and の中の or の中の Condition の 3 段の条件を、ケースの目印つきで返す。"""
    return {
        "op": "and",
        "items": [
            {"field": "case", "op": "eq", "value": marker},
            {"op": "or", "items": [{"field": "tag", "op": "eq", "value": "a"}, {"field": "tag", "op": "ne", "value": "b"}]},
        ],
    }


def call_text(tool: str, marker: str, extra: str = "") -> str:
    """ツールを 1 回呼ばせる指示の文を返す。"""
    return (
        f"Call the MCP tool `{tool}` exactly once with this exact `filter` argument (JSON, keep the structure as is): "
        f"{json.dumps(filter_for(marker))}{extra}. Do not call any other MCP tool. Then reply with the tool result only."
    )


def make_workspace(base: Path) -> tuple[Path, Path, Path, Path]:
    """git リポジトリ・下のフォルダ・ワークツリー・外のフォルダを作る。"""
    root = base / "repo"
    sub = root / "sub"
    outside = base / "outside"
    sub.mkdir(parents=True)
    outside.mkdir()
    (sub / "a.txt").write_text("a\n", encoding="utf-8")
    git = ["git", "-c", "user.name=poc", "-c", "user.email=poc@example.com"]
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run([*git, "add", "."], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], cwd=root, check=True)
    worktree = root / ".claude" / "worktrees" / "x"
    subprocess.run([*git, "worktree", "add", "-q", "-b", "x", "--", str(worktree)], cwd=root, check=True)
    return root, sub, worktree, outside


def build_cases(root: Path, sub: Path, worktree: Path, outside: Path) -> list[Case]:
    """成功条件ごとのケースを並べる。"""
    probe_only = (PROBE,)
    with_cd = (PROBE, "Bash(cd:*)")
    cd = "First run the Bash command `cd {path}` (only that command). Then "
    return [
        Case(name="launch-root", cwd=root, prompt=call_text(PROBE, "launch-root"), allowed=probe_only, expected_cwd=root),
        Case(name="launch-sub", cwd=sub, prompt=call_text(PROBE, "launch-sub"), allowed=probe_only, expected_cwd=sub),
        Case(name="cd-sub", cwd=root, prompt=cd.format(path=sub) + call_text(PROBE, "cd-sub"), allowed=with_cd, expected_cwd=sub),
        Case(name="cd-worktree", cwd=root, prompt=cd.format(path=worktree) + call_text(PROBE, "cd-worktree"), allowed=with_cd, expected_cwd=worktree),
        Case(name="cd-outside", cwd=root, prompt=cd.format(path=outside) + call_text(PROBE, "cd-outside"), allowed=with_cd, expected_cwd=None),
        Case(
            name="override",
            cwd=root,
            prompt=call_text(PROBE, "override", ', and also pass `cwd` = "/tmp/fake", `session_id` = "fake-session", `agent_id` = "fake-agent"'),
            allowed=probe_only,
            expected_cwd=root,
        ),
        Case(
            name="subagent",
            cwd=root,
            prompt=(
                "Do not call any MCP tool yourself. Use the Agent tool once (subagent_type general-purpose) and instruct the subagent: "
                + call_text(PROBE, "subagent")
            ),
            allowed=(PROBE, "Agent", "Task"),
            expected_cwd=root,
        ),
        Case(name="delete", cwd=root, prompt=call_text(PROBE_DELETE, "delete"), allowed=probe_only, expected_cwd=None),
    ]


def wait_port(port: int) -> None:
    """サーバーがポートで待ち受けるまで待つ。"""
    deadline = time.monotonic() + SERVER_START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        with socket.socket() as s:
            # 繋がった: 待ち受けている
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"サーバーが {SERVER_START_TIMEOUT_SEC} 秒で起動しませんでした: port={port}")


def run_case(case: Case, plugin: Path, out: Path, env: dict[str, str]) -> None:
    """claude -p を 1 回流し、出力を claude-{名前}.json に残す。"""
    command = [
        "claude", "-p", case.prompt,
        "--plugin-dir", str(plugin),
        "--setting-sources", "project",
        "--permission-mode", "default",
        "--output-format", "json",
        "--allowedTools", *case.allowed,
    ]
    result = subprocess.run(command, cwd=case.cwd, env=env, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_SEC, check=False)
    (out / f"claude-{case.name}.json").write_text(result.stdout + ("\n--- stderr ---\n" + result.stderr if result.stderr else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    """JSON Lines を読む。無ければ空。"""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def marker_of(filter_value: object) -> str | None:
    """条件の木からケースの目印を取り出す。"""
    if not isinstance(filter_value, dict):
        return None
    for item in filter_value.get("items", []):
        # 先頭の Condition がケースの目印を持つ
        if isinstance(item, dict) and item.get("field") == "case":
            return str(item.get("value"))
    return None


def evaluate(cases: list[Case], out: Path) -> list[tuple[str, bool, str]]:
    """args.jsonl と hook.jsonl を突き合わせ、成功条件ごとの合否を返す。"""
    args_rows = read_jsonl(out / "args.jsonl")
    hook_rows = read_jsonl(out / "hook.jsonl")
    by_case_args = {marker_of(r["filter"]): r for r in args_rows}
    by_case_hook = {marker_of(r["tool_input"].get("filter")): r for r in hook_rows}
    results: list[tuple[str, bool, str]] = []

    def pair(name: str) -> tuple[dict | None, dict | None]:
        return by_case_args.get(name), by_case_hook.get(name)

    # cwd: 起動したフォルダ・cd の後
    for case in cases:
        if case.expected_cwd is None or case.name in ("override", "subagent"):
            continue
        got, hook = pair(case.name)
        ok = got is not None and hook is not None and got["cwd"] == str(case.expected_cwd) == hook["cwd"]
        results.append((f"cwd（{case.name}）", ok, f"expected={case.expected_cwd} args={got and got['cwd']} hook={hook and hook['cwd']}"))

    # cwd: 外へ cd（判定せず記録する）
    got, hook = pair("cd-outside")
    results.append(("cwd（cd-outside・記録）", True, f"args.cwd={got and got['cwd']} hook.cwd={hook and hook['cwd']} CLAUDE_PROJECT_DIR={hook and hook['claude_project_dir']}"))

    # session_id: フックの入力と一致し、空でない
    rows = [pair(c.name) for c in cases if c.name != "delete"]
    ok = all(g is not None and h is not None and g["session_id"] and g["session_id"] == h["session_id"] for g, h in rows)
    results.append(("session_id がフックの入力と一致", ok, json.dumps([(g and g["session_id"], h and h["session_id"]) for g, h in rows])))

    # agent_id: メインでは空、サブエージェントでは空でなくフックの入力と一致
    main_rows = [pair(c.name) for c in cases if c.name not in ("delete", "subagent")]
    main_ok = all(g is not None and g["agent_id"] == "" for g, _ in main_rows)
    got, hook = pair("subagent")
    sub_ok = got is not None and hook is not None and bool(got["agent_id"]) and got["agent_id"] == hook["agent_id"]
    results.append(("agent_id（メインは空・サブエージェントは値）", main_ok and sub_ok, f"main={[g and g['agent_id'] for g, _ in main_rows]} sub.args={got and got['agent_id']} sub.hook={hook and hook['agent_id']} agent_type={hook and hook['agent_type']}"))

    # 引数の上書き: モデルが渡した偽の値がフックの値に置き換わる
    got, hook = pair("override")
    ok = got is not None and hook is not None and got["cwd"] == hook["cwd"] != "/tmp/fake" and got["session_id"] == hook["session_id"] and got["agent_id"] == ""
    results.append(("モデルが渡した値を上書き", ok, f"model={hook and {k: hook['tool_input'].get(k) for k in ('cwd', 'session_id', 'agent_id')}} args={got and {k: got[k] for k in ('cwd', 'session_id', 'agent_id')}}"))

    # 許可の確認を保つ: 許可していない probe_delete はサーバーに届かない
    reached = [r for r in args_rows if r["tool"] == "probe_delete"]
    hooked = [r for r in hook_rows if r["tool_name"] == PROBE_DELETE]
    results.append(("許可していない probe_delete が届かない", not reached, f"server_rows={len(reached)} hook_rows={len(hooked)}"))

    # 他の引数を保つ・再帰する入力スキーマ: 3 段の木が指示どおりに届く
    for case in cases:
        if case.name == "delete":
            continue
        got, _ = pair(case.name)
        ok = got is not None and got["filter"] == filter_for(case.name)
        results.append((f"filter の 3 段の木（{case.name}）", ok, json.dumps(got and got["filter"], ensure_ascii=False)))

    tools = json.loads((out / "tools.json").read_text(encoding="utf-8"))
    has_ref = "$ref" in json.dumps(tools["probe"])
    results.append(("入力スキーマが $ref で再帰する", has_ref, json.dumps(tools["probe"].get("$defs", {}).get("Group", {}), ensure_ascii=False)))
    return results


def main() -> int:
    """サーバーを立てて全ケースを流し、結果を run.log に書く。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--maintain-project-dir", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    # 前の実行のログを消す
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    port = free_port()
    server = subprocess.Popen([sys.executable, str(HERE / "server.py"), "--port", str(port), "--log-dir", str(out)])
    try:
        wait_port(port)
        with tempfile.TemporaryDirectory() as tmp:
            root, sub, worktree, outside = make_workspace(Path(tmp).resolve())
            env = {k: v for k, v in os.environ.items() if k != MAINTAIN_ENV}
            env.update({"POC_DOCS_PORT": str(port), "POC_LOG_DIR": str(out)})
            # 指定したときだけ、cd を起動フォルダへ戻す環境変数を立てる
            if args.maintain_project_dir:
                env[MAINTAIN_ENV] = "1"
            cases = build_cases(root, sub, worktree, outside)
            for case in cases:
                print(f"実行: {case.name}", flush=True)
                run_case(case, HERE / "plugin", out, env)
            results = evaluate(cases, out)
    finally:
        server.terminate()
        server.wait()

    lines = [f"{MAINTAIN_ENV}={'1' if args.maintain_project_dir else '(なし)'}"]
    lines += [f"{'OK' if ok else 'NG'} {label}: {detail}" for label, ok, detail in results]
    (out / "run.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
