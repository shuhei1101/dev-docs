# 設計書のスキーマの参照を design-schemas の v9 系へ上げ、設計書の refs を related へ書き換える

## 概要

設計書の行のスキーマの参照を knowledge の design-schemas の v9 系の最新のタグへ上げ、全ての設計書の `refs` を `related` の記載方法へ書き換えて、全ての文書の検査に合格させる。

## 背景

[Issue #263](https://github.com/shuhei1101/dev-docs/issues/263) の要望。
knowledge の `design-schemas/v9.0.0` で、設計書の `refs` の要素が、関係の種類 `type` と参照する条件 `when` を持つ関連の要素（`related`）へ変わった（[shuhei1101/knowledge の 8b2f90a](https://github.com/shuhei1101/knowledge/commit/8b2f90a)）。
[#261](https://github.com/shuhei1101/dev-docs/pull/261)（起点 Issue [#198](https://github.com/shuhei1101/dev-docs/issues/198)）はスキーマの参照を v8.4.0 までだけ上げ、v9 系への版上げをこの Issue へ切り出した。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [要件.yaml](./要件.yaml) | 更新ドキュメント・スコープ外 |
| [タスク一覧](./タスク一覧.yaml) | 工程ごとの状態 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 配信元の設定と、サーバー・全体に関わる設計書の計画書 |
| [画面](./画面.md) | 画面の設計書の計画書 |
