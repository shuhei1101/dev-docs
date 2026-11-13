# 端末の設定のスキーマ（settings.schema.yaml）の title・description の文言を、AI slop の単語の対応表に合わせて修正する

## 概要

dev-docs の端末の設定のスキーマ `src/dev_docs/schemas/settings.schema.yaml` の `title`・`description` の文言を、AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #151](https://github.com/shuhei1101/dev-docs/issues/151) の要望。[PR #148](https://github.com/shuhei1101/dev-docs/pull/148) のレビューで、`templates/` と同じ型（JSON Schema の `title`・`description`）の文言がサーバーのスキーマに残っていると指摘を受けて切り出した。
起票の後に [PR #163](https://github.com/shuhei1101/dev-docs/pull/163) で `dev-docs.schema.yaml`・`schemas/dev-docs.schema.json` と端末の設定の配信元のキーが project-index へ移り、dev-docs に残る対象は `settings.schema.yaml` だけになった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
