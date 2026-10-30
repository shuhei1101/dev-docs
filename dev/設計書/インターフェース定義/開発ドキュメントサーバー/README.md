# 開発ドキュメントサーバー

開発ドキュメントサーバーの MCP ツール・管理の MCP・画面の API・設定と起動のインターフェース

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
| 管理の MCP | [状態の取得](./状態の取得.yaml) | status |
| 管理の MCP | [設定の読み直し](./設定の読み直し.yaml) | reload |
| 管理の MCP | [再起動](./再起動.yaml) | restart |
| 管理の MCP | [更新](./更新.yaml) | update |
| 管理の MCP | [配信元の検査](./配信元の検査.yaml) | check_project |
| 管理の MCP | [試しの変換](./試しの変換.yaml) | try_convert |
| 画面の API | [文書の取得](./文書の取得.yaml) | GET /_api/sources/{source}/docs[/{path}] |
| 画面の API | [画面の検索](./画面の検索.yaml) | GET /_api/sources/{source}/search |
| 画面の API | [リビジョンの一覧](./リビジョンの一覧.yaml) | GET /_api/sources/{source}/refs |
| 画面の API | [表の列の設定の保存](./表の列の設定の保存.yaml) | PUT /_api/sources/{source}/columns |
| 画面の API | [APIのスキーマ](./APIのスキーマ.yaml) | GET /_api/openapi.json |
| 設定・起動 | [端末の設定の取得](./端末の設定の取得.yaml) | GET /_api/settings/sources |
| 設定・起動 | [端末の設定の保存](./端末の設定の保存.yaml) | PUT /_api/settings/sources |
| 設定・起動 | [起動](./起動.yaml) | dev-docs serve |
| 設定・起動 | [設定の移し替え](./設定の移し替え.yaml) | dev-docs migrate |
| 設定・起動 | [セッションの文脈](./セッションの文脈.yaml) | POST /_admin/session-context |
| 設定・起動 | [載せるファイルの一覧](./載せるファイルの一覧.yaml) | dev-docs files |
| 画面の API | [画面の配信](./画面の配信.yaml) | GET /{path} |

<!-- /table -->
