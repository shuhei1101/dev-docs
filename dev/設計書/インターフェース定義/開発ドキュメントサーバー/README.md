# 開発ドキュメントサーバー

開発ドキュメントサーバーの MCP ツール・画面の API・起動のインターフェース

## 目次

<!-- table: data -->

| 分類 | ページ | 概要 |
| --- | --- | --- |
| MCP | [文書の検索](./文書の検索.yaml) | search_docs |
| MCP | [文書の書き込み](./文書の書き込み.yaml) | write_docs |
| MCP | [文書の削除](./文書の削除.yaml) | delete_docs |
| MCP | [配信元の説明](./配信元の説明.yaml) | describe |
| MCP | [変更の一覧](./変更の一覧.yaml) | list_changes |
| MCP | [関連のたどり](./関連のたどり.yaml) | trace_related |
| 画面の API | [文書の取得](./文書の取得.yaml) | GET /_api/sources/{source}/docs[/{path}] |
| 画面の API | [画面の検索](./画面の検索.yaml) | GET /_api/sources/{source}/search |
| 画面の API | [リビジョンの一覧](./リビジョンの一覧.yaml) | GET /_api/sources/{source}/refs |
| 画面の API | [表の列の設定の保存](./表の列の設定の保存.yaml) | PUT /_api/sources/{source}/columns |
| 設定・起動 | [端末の設定の取得](./端末の設定の取得.yaml) | GET /_api/settings/sources |
| 設定・起動 | [端末の設定の保存](./端末の設定の保存.yaml) | PUT /_api/settings/sources |
| 設定・起動 | [起動](./起動.yaml) | dev-docs serve |
| 画面の API | [APIのスキーマ](./APIのスキーマ.yaml) | GET /_api/openapi.json |

<!-- /table -->
