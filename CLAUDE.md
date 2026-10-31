# dev-docs

YAML の正本を読み、人が読む画面と文書の MCP（HTTP）を出す汎用の開発ドキュメントサーバー。各リポジトリは設定ファイルを渡して起動する。

## ドキュメント

実体は開発ドキュメント [dev/](./dev/) と公開ドキュメント [docs/](./docs/) にある。
使い方は [使い方](./docs/使い方/)。

着手前に索引を引いて読む。

```bash
PROJECT_ROOT="$PWD" PYTHONPATH="$AI_MONITOR_HOME/src" python3 -m ai_monitor.inject.build_docs_index
```

## 画面（`frontend/`）

画面は `frontend/` の React（Vite）の SPA で、構成は [画面のモジュール構成](./dev/設計書/モジュール構成/画面/分類/) に従う。
`frontend/src` は `app/`・`routes/`・`features/`・`shared/`・`testing/` に分け、import の向きは eslint-plugin-boundaries で検査する。
React と画面の設計は、[knowledge](https://github.com/shuhei1101/knowledge/tree/develop/docs/rule) の `react-*.yaml`（React）と `ui-*.yaml`（ui）に従う。
着手前に Read で読む。
