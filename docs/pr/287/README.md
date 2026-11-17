# 変換の項目のパスの解釈（ITEM_STEP）を、[...] の中の対応の取れた [ ] を値の一部にする書き方に追随させる

## 概要

文書の参照（`id:{ID}#{項目のパス}`）の項目のパスで `x-key` の値に `[` `]` を含む要素（`request[operations[].fields]` など）を指したとき、画面の変換がその要素の見出しを解けるようにする。

## 背景

[Issue #281](https://github.com/shuhei1101/dev-docs/issues/281) の要望。
[shuhei1101/project-index#169](https://github.com/shuhei1101/project-index/pull/169)（起点 Issue [shuhei1101/project-index#167](https://github.com/shuhei1101/project-index/issues/167)）で、`write_docs` の参照の型の項目のパスは `[...]` の中の対応の取れた `[` `]` を値の一部として扱うようになった。
develop の `src/dev_docs/features/convert/markdown.py` の `ITEM_STEP` は `[...]` の中の最初の `]` で値を切るため、`[` `]` を含む値を指す項目のパスの見出しを解けない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
