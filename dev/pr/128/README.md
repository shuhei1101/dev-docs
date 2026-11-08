# 設計書のデータの図を新しいスキーマのキー（kind・frame・hint・tip・line・ER 図の両端の列と多重度）で描画する

## 概要

利用者が、AI Monitor の新しいスキーマで記載した設計書の図（判定・データフロー・アーキテクチャ・状態遷移・ER 図）を、画面で mdmark の部品として参照できるようになる。

## 背景

[#118](https://github.com/shuhei1101/dev-docs/issues/118) の要望。
[shuhei1101/ai-monitor#3222](https://github.com/shuhei1101/ai-monitor/pull/3222) で、設計書のスキーマのデータの図のキーが規約『表し方の優先順位』に合わせて変わった（ノードの `shape` を削除して `kind` に判定の種類を追加、辺の `line` を意味の値へ、`subgraphs` を `frame` へ、ER 図の関連を両端の列と多重度へ）。
dev-docs の変換（`features/convert/diagrams.py`）は古いキーから mdmark の部品の定義を推定していて、新しいキーで記載した図を描画できない。

画面が参照する mdmark の切り替えは [#127](https://github.com/shuhei1101/dev-docs/issues/127) が受け持ち、この PR では今の `mdmark@master`（v0.10.0 と同じ commit）で描画を確認する。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
