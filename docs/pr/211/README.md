# 画面のサーバーの共通のキーの組み立てを、project-index の文書の一覧の commonKeys に切り替える

## 概要

画面のサーバーが共通のキーを自前で組み立てる処理を削除し、project-index が解決した共通のキー（`commonKeys`）をそのまま使用する。

## 背景

[Issue #191](https://github.com/shuhei1101/dev-docs/issues/191) の要望。[shuhei1101/project-index#54](https://github.com/shuhei1101/project-index/pull/54) のスコープ外の項目を切り出したもの。

[#183](https://github.com/shuhei1101/dev-docs/pull/183) で、画面のサーバーは配信元の設定の行の `metadata`・`alias_type` と文書の一覧の `value` から、project-index の `resolve_metadata` と同じ規則で共通のキー（`METADATA_KEYS`）を組み立てるようになった。
同じ規則を 2 つのリポジトリが持つため、project-index だけで `METADATA_KEYS` が増えると食い違う（project-index の develop の `METADATA_KEYS` は既に `visibility` を持ち、dev-docs は持たない）。
project-index#54 で、文書の一覧の `common_keys=true` が `documents[].commonKeys` を、文書の取得が `metadata.commonKeys` を返すようになった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
