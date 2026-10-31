# 開発ドキュメントサーバー

開発ドキュメントサーバー（`src/dev_docs`）の分類ごとの構成

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [__init__.py](./__init__.py.yaml) | インストール済みのパッケージからバージョンを引くときの配布名 |
| [__main__.py](./__main__.py.yaml) | `dev-docs` コマンドの引数の組み立てと main |
| [main.py](./main.py.yaml) | `dev-docs serve`・`dev-docs migrate` の部品の配線と、配信元の読み直し |
| [分類](./分類/) | 分類ごとのファイルのツリーと構成図 |
| [features](./features/) | 文書の読み込み・検査・変換・検索・書き込み・履歴と、画面の API・管理の MCP・再起動と更新・設定の移し替え |
| [server](./server/) | アプリの組み立て・例外の変換・MCP のセッションの管理・画面の配信と、文書の MCP・管理の MCP |
| [shared](./shared/) | 例外の階層・YAML の読み書き・ファイルの置き換え・ハッシュ・パスの照合・API の DTO の基底 |
| [integrations](./integrations/) | git の実行とスクリプトの実行 |

<!-- /table -->
