# 図の配置（flow_layout.py）を、mdmark の定義の検査で線が他のノードを横切らず、文字がノードに収まる配置へ修正する

## 概要

フロー図の配置（`layout_flow`）を、mdmark の定義の検査の配置のずれ（`diagram_wire_crosses_node`・`diagram_label_too_long`・`diagram_node_overflow`）が 0 件になる配置へ修正する。

## 背景

[#162](https://github.com/shuhei1101/dev-docs/issues/162) の要望。
[shuhei1101/ai-monitor#3356](https://github.com/shuhei1101/ai-monitor/pull/3356) で、dev-docs と同じ配置にしていた ai-monitor の図を mdmark v0.10.0 の定義の検査にかけたところ、`flow` の図 15 件のうち 13 件にずれが出た。
dev-docs の `src/dev_docs/features/convert/flow_layout.py` も同じ配置のため、同じずれを持つ。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
