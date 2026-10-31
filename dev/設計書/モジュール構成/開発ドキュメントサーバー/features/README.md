# features

文書の読み込み・検査・変換・検索・書き込み・履歴と、画面の API・管理の MCP・再起動と更新・設定の移し替え

## 目次

| ページ | 概要 |
| --- | --- |
| [documents](./documents/) | 文書のファイルの収集と、メタデータ・バージョン・日時を付けた文書 |
| [sources](./sources/) | 配信元の設定のマージと検証、配信する配信元の一覧 |
| [settings](./settings/) | 端末の設定の検証と読み込み、`sources[]` の取得と保存 |
| [access](./access/) | 作業場所からの権限と、MCP の引数からの読み書きする場所の解決 |
| [validation](./validation/) | スキーマ・ID の形・関連の種類・`validators[]` による文書の検査 |
| [convert](./convert/) | スキーマ駆動か `converters[]` による文書の Markdown への変換 |
| [history](./history/) | git によるリビジョンの解決・一覧・変わったファイル・ファイルの日時 |
| [seen](./seen/) | 会話キーごとの返し済み・前回読んだ内容・閲覧と編集の記録 |
| [search](./search/) | `search_docs` の条件の木・並べ替え・集計・量の上限 |
| [write](./write/) | `write_docs`・`delete_docs` の操作の適用・検査・書き換え |
| [changes](./changes/) | `list_changes` の区間か前回読んだ時点からの変わった文書と差分 |
| [related](./related/) | `trace_related` の関連のたどりと関連の候補 |
| [describe](./describe/) | `describe` の使える配信元・説明書と種類・種類のスキーマ |
| [view](./view/) | 文書の取得・画面の検索・リビジョンの一覧・表の列の設定の API |
| [admin](./admin/) | 管理の MCP の状態・読み直し・検査・試しの変換 |
| [session_context](./session_context/) | `POST /_admin/session-context` のセッションの文脈 |
| [lifecycle](./lifecycle/) | 再起動の制御とクローンの更新 |
| [migrate](./migrate/) | `dev-docs migrate` の設定の移し替え |
| [prompt_doc](./prompt_doc/) | `dev-docs prompt-doc` のプロンプトの YAML の Markdown への変換 |
