# server

アプリの組み立て・例外の変換・MCP のセッションの管理・画面の配信と、文書の MCP・管理の MCP

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [app.py](./app.py.yaml) | ルートと MCP のマウントをまとめたアプリの組み立て |
| [error_handlers.py](./error_handlers.py.yaml) | 例外の problem+json への変換 |
| [lifespan.py](./lifespan.py.yaml) | MCP のセッションの管理と、記録の削除 |
| [origin.py](./origin.py.yaml) | 画面と同じオリジンからの要求かの確認 |
| [screen.py](./screen.py.yaml) | 画面のビルドの配信 |
| [mcp](./mcp/) | 文書の MCP と管理の MCP の組み立てと、ツールの結果・エラーの変換 |

<!-- /table -->
