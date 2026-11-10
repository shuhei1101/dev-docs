# interface

サブシステムの外部インターフェースと処理フロー（結合テストの元）

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [APIのスキーマ](./IF-155-3.yaml) | GET /_api/openapi.json |
| [セッションの開始](./IF-155-4.yaml) | POST /_admin/session-start |
| [セッション開始のフック](./IF-155-1.yaml) | SessionStart |
| [ツール実行前のフック](./IF-155-2.yaml) | PreToolUse |
| [プロンプトの文書の変換](./IF-155-5.yaml) | dev-docs prompt-doc |
| [リビジョンの一覧](./IF-155-6.yaml) | GET /_api/sources/{source}/refs |
| [再起動](./IF-155-7.yaml) | restart |
| [変更の一覧](./IF-155-8.yaml) | list_changes |
| [文書の削除](./IF-155-9.yaml) | delete_docs |
| [文書の取得](./IF-155-10.yaml) | GET /_api/sources/{source}/docs[/{path}] |
| [文書の書き込み](./IF-155-11.yaml) | write_docs |
| [文書の検索](./IF-155-12.yaml) | search_docs |
| [更新](./IF-155-13.yaml) | update |
| [状態の取得](./IF-155-14.yaml) | status |
| [用語の一覧](./IF-155-15.yaml) | list_match_words |
| [画面の検索](./IF-155-16.yaml) | GET /_api/sources/{source}/search |
| [画面の構成の書き込み](./IF-155-17.yaml) | write_nav |
| [画面の配信](./IF-155-18.yaml) | GET /{path} |
| [端末の設定の保存](./IF-155-19.yaml) | PUT /_api/settings/sources |
| [端末の設定の取得](./IF-155-20.yaml) | GET /_api/settings/sources |
| [表の列の設定の保存](./IF-155-21.yaml) | PUT /_api/sources/{source}/columns |
| [設定の移し替え](./IF-155-22.yaml) | dev-docs migrate |
| [設定の読み直し](./IF-155-23.yaml) | reload |
| [試しの変換](./IF-155-24.yaml) | try_convert |
| [起動](./IF-155-25.yaml) | dev-docs serve |
| [載せるファイルの一覧](./IF-155-26.yaml) | dev-docs files |
| [配信元の検査](./IF-155-27.yaml) | check_project |
| [配信元の説明](./IF-155-28.yaml) | describe |
| [関連のたどり](./IF-155-29.yaml) | trace_related |

<!-- /table -->
