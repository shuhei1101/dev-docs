# interface

サブシステムの外部インターフェースと処理フロー（結合テストの元）

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [APIのスキーマ](./IF-155-3.yaml) | GET /_api/openapi.json |
| [セッション開始のフック](./IF-155-1.yaml) | SessionStart |
| [リビジョンの一覧](./IF-155-6.yaml) | GET /_api/sources/{source}/refs |
| [再起動](./IF-155-7.yaml) | restart |
| [文書の取得](./IF-155-10.yaml) | GET /_api/sources/{source}/docs[/{path}] |
| [更新](./IF-155-13.yaml) | update |
| [状態の取得](./IF-155-14.yaml) | status |
| [画面の検索](./IF-155-16.yaml) | GET /_api/sources/{source}/search |
| [画面の配信](./IF-155-18.yaml) | GET /{path} |
| [端末の設定の保存](./IF-155-19.yaml) | PUT /_api/settings/sources |
| [端末の設定の取得](./IF-155-20.yaml) | GET /_api/settings/sources |
| [表の列の設定の保存](./IF-155-21.yaml) | PUT /_api/sources/{source}/columns |
| [設定の移し替え](./IF-155-22.yaml) | dev-docs migrate |
| [起動](./IF-155-25.yaml) | dev-docs serve |

<!-- /table -->
