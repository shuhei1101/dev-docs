# dev-docs

project-index が配信している配信元の文書を、人が読む画面で出す開発ドキュメントサーバー。
文書とソースコードの索引・検索・書き込みの MCP は [project-index](https://github.com/shuhei1101/project-index) が持つ。検索の MCP だけを使う端末は project-index だけを入れ、画面を使う端末にだけ dev-docs を入れる。
配信元の設定の既定のファイル名は `project-index.yaml`（Git 管理外の値は `project-index.local.yaml`）。
dev-docs 自身の `docs/` の文書は、直下の `project-index.yaml` で配信元 `dev-docs` として配信する。

## 導入

Claude Code にプラグイン `dev-docs` をユーザースコープで入れ、`/dev-docs:global-setup` で端末の設定と起動を用意します。
手順は [dev-docsを入れる](docs/guide/dev-docsを入れる.md) にあります。

## 画面

サーバーを起動したら、ブラウザで `http://127.0.0.1:{port}/` を開きます（既定は `http://127.0.0.1:8781/`）。
使い方は [画面で読む](docs/guide/画面で読む.md) にあります。

## 画面の開発

画面は `frontend/` の React（Vite）の SPA です。
ビルドの成果物は `src/dev_docs/screen/` に置いて commit します。
開発のコマンドは、直下の `package.json` の npm scripts にあります（[開発コマンド](docs/dev-command/)）。
lefthook の pre-commit が、`frontend/**` の変更で画面をビルドし直して `src/dev_docs/screen/` をステージへ戻します。

ドキュメント: https://shuhei1101.github.io/dev-docs/
