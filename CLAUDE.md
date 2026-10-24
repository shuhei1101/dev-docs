# dev-docs

YAML の正本を読み、人が読む画面と文書の MCP（HTTP）を出す汎用の開発ドキュメントサーバー。各リポジトリは設定ファイルを渡して起動する。

## ドキュメント

実体は開発ドキュメント [dev/](./dev/) と公開ドキュメント [docs/](./docs/) にある。
使い方は [使い方](./docs/使い方/)。

着手前に索引を引いて読む。

```bash
PROJECT_ROOT="$PWD" PYTHONPATH="$AI_MONITOR_HOME/src" python3 -m ai_monitor.inject.build_docs_index
```
