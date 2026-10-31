"""4 つの配信元がメインのリポジトリの dev-docs.yaml から配信され、develop のワークツリーを一覧に載せているかを読むだけで確かめる。"""

import sys

from mcp_client import ADMIN_MCP_URL, DOCS_MCP_URL, REPLACEMENTS, SETTINGS, call_tool

# 書き換え先の config の順に並べた配信元の ID（dev-docs.yaml の name）
SOURCE_IDS = ["shuhdev-gateway", "claude-balancer", "alias-inject", "rule-inject"]
DEVELOP_WORKTREE = ".claude/worktrees/develop"


def main() -> int:
    """端末の設定・status・describe(source) を観測し、項目ごとに結果の行を出す。"""
    results: list[tuple[str, bool, str]] = []

    # 端末の設定が 4 つのメインのリポジトリの dev-docs.yaml を指しているか
    settings = SETTINGS.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        results.append(
            (f"config {new}", f"config: {new}\n" in settings and old not in settings, "")
        )

    # 読み直した後のサーバーが 4 つを配信しているか
    status = call_tool(ADMIN_MCP_URL, "status", {})
    for source_id in SOURCE_IDS:
        row = next(
            (line for line in status.splitlines() if line.startswith(f"| {source_id} |")), ""
        )
        results.append((f"status {source_id}", "| serving |" in row, row))

    # 配信元の説明書のワークツリーの一覧に develop のワークツリーが載っているか
    for source_id in SOURCE_IDS:
        guide = call_tool(DOCS_MCP_URL, "describe", {"source": source_id})
        rows = [line for line in guide.splitlines() if DEVELOP_WORKTREE in line]
        results.append((f"describe {source_id}", bool(rows), " ".join(rows)))

    for name, ok, observed in results:
        suffix = f" ({observed})" if observed else ""
        print(f"{name}: {'ok' if ok else 'failed'}{suffix}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
