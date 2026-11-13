# 共有の UI 部品の destructive のコントラストと transition の指定を修正する

## 概要

利用者が設定画面の状態のバッジ「配信停止」と削除のボタンを基準どおりのコントラストで読め、設定画面の部品が高さを transition で動かさなくなる。

## 背景

[#185](https://github.com/shuhei1101/dev-docs/issues/185) の束（[#165](https://github.com/shuhei1101/dev-docs/issues/165)・[#166](https://github.com/shuhei1101/dev-docs/issues/166)）。どちらも作業 PR [#163](https://github.com/shuhei1101/dev-docs/pull/163) のモック作成のレビューで、対象外の逸脱として報告された。

- #165: axe の `color-contrast`（serious）が設定画面の状態のバッジ「配信停止」に当たった。`badge.tsx` の `destructive`（`bg-destructive/10 text-destructive`）で、`button.tsx` の `destructive` も同じ指定を持つ
- #166: Impeccable の `layout-transition`（`transition: height`）が設定画面のストーリー（390x844）で検出された。`frontend/src/shared/components/ui/` の `transition-all` を持つ部品（`badge.tsx`・`button.tsx`・`switch.tsx`・`tabs.tsx`）が候補

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響範囲 |
| [画面](./画面.md) | 共有の UI 部品の色と transition の指定の修正の計画書 |
