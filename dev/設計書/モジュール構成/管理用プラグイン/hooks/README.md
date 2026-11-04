# hooks

SessionStart・PreToolUse のフック

## 目次

| ページ | 概要 |
| --- | --- |
| [session_start.py](./session_start.py.yaml) | サーバーの起動と、`/clear`・圧縮のときの返し済みの記録の削除の依頼 |
| [pre_tool_use.py](./pre_tool_use.py.yaml) | 文書の MCP のツールの入力への `cwd`・`session_id`・`agent_id` の上書き |
