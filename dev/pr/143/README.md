# MCP のツールの引数の説明と CLI の出力の文言を、AI slop の単語の対応表に合わせて修正する

## 概要

`src/dev_docs/` が MCP のツールの引数の説明・ツールの説明としてエージェントに表示する文言と、CLI が端末に出すヘルプ・エラー・`prompt-doc` が生成する文書の文言を、knowledge の AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #142](https://github.com/shuhei1101/dev-docs/issues/142)（[#139](https://github.com/shuhei1101/dev-docs/issues/139)・[#140](https://github.com/shuhei1101/dev-docs/issues/140) の束）の要望。
[PR #133](https://github.com/shuhei1101/dev-docs/pull/133)（起点 [Issue #117](https://github.com/shuhei1101/dev-docs/issues/117)）は MCP の応答の文言を修正し、入力スキーマの説明と CLI の出力をスコープ外として #139・#140 に切り出した。
PR #133 の後、同じ意味の文言が、MCP の応答では `参照する`・`指定する`、引数の説明では `読む`・`渡す` のように 2 通りになっている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
