# 公開ページのビルドが受け付ける分類を設計書どおり「使用方法」にし、pages.yml の失敗を修正する

## 概要

公開ページのビルド `scripts/build_pages.py` が公開ドキュメントの分類 `使用方法` を受け付け、公開ページの配信の workflow `pages.yml` が成功するようにする。

## 背景

[#285](https://github.com/shuhei1101/dev-docs/issues/285) の要望。
`pages.yml` の step「公開の文書を 1 枚の HTML にまとめる」が `docs/guide/dev-docsを導入する.md: 分類が はじめに・使い方・リファレンス のどれでもありません` で失敗し、公開ページが develop の最新で配信されない。

[#248](https://github.com/shuhei1101/dev-docs/pull/248) が `docs/guide/files.yml` とモジュール構成 `MOD-192-1.py.yaml` の分類を `使い方` から `使用方法` へ書き換え、`scripts/build_pages.py` と単体テストが `使い方` のまま残った。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |

変更が及ぶ実装（開発用のスクリプト）と配信の設定 `project-index.yaml` は、アーキテクチャ図のサブシステムに属さないため、対象システムの計画書を作らない。
