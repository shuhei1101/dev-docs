# 変換の項目の見出し（item_heading）で、[{値}#{順番}] と辞書の [{キー}] を見出しに解けるようにする

## 概要

文書の参照（`id:{ID}#{項目のパス}`）の項目のパスで、同じ値の要素の 2 つ目以降（`[{値}#{順番}]`）と辞書の項目（`[{キー}]`）を指したとき、画面の変換がその見出しを解けるようにする。

## 背景

[Issue #288](https://github.com/shuhei1101/dev-docs/issues/288) の要望。[#287](https://github.com/shuhei1101/dev-docs/pull/287)（起点 Issue [#281](https://github.com/shuhei1101/dev-docs/issues/281)）のスコープ外から切り出した。
knowledge の共通の型 `ref` は `functions[main#3]`・`notes[main.py の補足]` の書き方を持つが、develop の `src/dev_docs/features/convert/markdown.py` の `item_heading` はどちらも `None` を返す。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
