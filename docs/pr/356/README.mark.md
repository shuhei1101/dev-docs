# 画面設計書・部品設計書を design-schemas/v12.0.0 の新規の欄で記載し直し、気づいた設計の漏れを実装とテストまで修正する

## 概要

設計書のスキーマの参照を `design-schemas/v12.0.0` へ上げ、画面設計書・部品設計書を新規の欄で記載し直す。
記載し直す途中で気づいた設計の漏れ・誤りは、設計を修正して画面の実装とテストまで合わせる。

## 背景

[Issue #355](https://github.com/shuhei1101/dev-docs/issues/355) の要望。
knowledge の `design-schemas/v12.0.0`（[shuhei1101/knowledge#602](https://github.com/shuhei1101/knowledge/issues/602)・[shuhei1101/knowledge#605](https://github.com/shuhei1101/knowledge/pull/605)）で、画面設計・部品設計に、規約にあるのに記載する欄が無かった決まりの欄が追加された。
今の画面設計書・部品設計書は新規のスキーマの必須の欄を持たず、`project-index.yaml` の `design-schemas` の参照（今は `v9.2.2`）を上げると検査に通らない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [画面](./画面.mark.md) | 画面の計画書 |
