# write_docs のツールの説明の結合テストの期待値と『文書の書き込み』の制約を、今の説明の文言に合わせる

## 概要

`write_docs` のツールの説明を確認する結合テストの期待値と、インターフェース定義『文書の書き込み』の「ツールの説明」の制約を、今の description の文言に合わせ、テストを pass させる。

## 背景

[#113](https://github.com/shuhei1101/dev-docs/issues/113) の要望。
[#105](https://github.com/shuhei1101/dev-docs/pull/105) で description の文言を「作成・削除・改名したら」に修正したが、テストと設計書は「作った・消した・改名したら」のままで、`test_normal_when_tool_description` が fail する。
[#111](https://github.com/shuhei1101/dev-docs/pull/111) の結合テストの実行で見つけた。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | インターフェース定義の制約と結合テストの期待値の修正 |
