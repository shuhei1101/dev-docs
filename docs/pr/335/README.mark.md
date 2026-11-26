# 文書の画面から、どの種類の文書の本文も編集して直コミットできるようにする

## 概要

利用者が、文書の画面から Markdown・YAML のどの種類の文書の本文も編集し、メタデータの画面と同じ差分確認を経て直コミットできるようにする。

## 背景

[Issue #330](https://github.com/shuhei1101/dev-docs/issues/330) の要望。
画面から直コミットできるのはメタデータの画面の表のセルだけで、規約・プロンプト・エージェントフロー・単語の対応表などの本文を修正するには、Claude Code のセッションで `write_docs` に `commit` を付けて頼むしかない。
[メタデータの取得](https://docs.shuhdev.com/dev-docs/docs/interface/IF-155-28.yaml?rev=develop)・[編集中の変更の直コミット](https://docs.shuhdev.com/dev-docs/docs/interface/IF-155-29.yaml?rev=develop) は修正できるキーを種類ごとに絞り、「規約の本文・テンプレート・スキーマは画面から書き換えない」と記載している（利用者が削除を決定済み）。
直コミットは、全ての配信元の `direct_commit.kinds` と端末の設定の `write_api_kinds` で全ての種類を許可済み。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 開発ドキュメントサーバーの計画書 |
| [画面](./画面.mark.md) | 画面の計画書 |
