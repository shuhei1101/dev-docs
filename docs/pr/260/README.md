# dev-docs 自身の YAML の設計書に tags を付け、project-index.yaml の設計書の行で検索できるようにする

## 概要

dev-docs 自身の YAML の設計書をタグで検索・集計できるようにする。

## 背景

[Issue #172](https://github.com/shuhei1101/dev-docs/issues/172) の要望。
[PR #171](https://github.com/shuhei1101/dev-docs/pull/171)（起点 Issue [#24](https://github.com/shuhei1101/dev-docs/issues/24)）で dev-docs 自身の `docs/` を `project-index.yaml` で配信するようにしたが、設計書の行の `metadata` は `name: title`・`description: lead` だけで、設計書は `tags` を持たない。
設計書のスキーマの `tags` は [PR #256](https://github.com/shuhei1101/dev-docs/pull/256)（AI Monitor v0.4.0 の配布物への追従）で knowledge の `design-schemas/v8.1.0` へ移り、記載できるようになった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、種類ごとのタグの主題 |
