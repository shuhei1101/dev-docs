# templates/ のスキーマと設定のひな形の文言を、AI slop の単語の対応表に合わせて修正する

## 概要

`templates/` のスキーマと設定のひな形の `title`・`description`・`examples`・コメントの文言を、knowledge の AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #144](https://github.com/shuhei1101/dev-docs/issues/144) の要望。
[PR #143](https://github.com/shuhei1101/dev-docs/pull/143)（起点 [Issue #142](https://github.com/shuhei1101/dev-docs/issues/142)）の現状調査で、同じ対応表にヒットする文言が `templates/` に残っているのが見つかった。
[PR #133](https://github.com/shuhei1101/dev-docs/pull/133)・PR #143 は MCP の応答・引数の説明・CLI の出力を修正し、`templates/` を対象にしていない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
