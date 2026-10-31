# dev-docs

YAML の正本を読み、文書の MCP（HTTP）と画面の API を出す汎用の開発ドキュメントサーバー。端末の設定に配信元を並べて起動する。

## 導入

Claude Code にプラグイン `dev-docs` をユーザースコープで入れ、`/dev-docs:global-setup` で端末の設定と起動を用意します。
手順は [dev-docsを入れる](docs/使い方/dev-docsを入れる.md) にあります。

## 画面

サーバーを起動したら、ブラウザで `http://127.0.0.1:{port}/` を開きます（既定は `http://127.0.0.1:8781/`）。
使い方は [画面で読む](docs/使い方/画面で読む.md) にあります。

## 画面の開発

画面は `frontend/` の React（Vite）の SPA です。
ビルドの成果物は `src/dev_docs/screen/` に置いて commit します。
開発のコマンドは、直下の `package.json` の npm scripts にあります（[開発コマンド](dev/設計書/開発コマンド/)）。
lefthook の pre-commit が、`frontend/**` の変更で検査を流し、画面をビルドし直して `src/dev_docs/screen/` をステージへ戻します。

ドキュメント: https://shuhei1101.github.io/dev-docs/
