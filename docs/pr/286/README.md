# 設定画面のダイアログのストーリーで検出される transition: height を出している要素とスタイルを特定して解消する

## 概要

設定画面のダイアログを開いたストーリーで検出される Impeccable の `layout-transition`（`transition: height`）について、出している要素とスタイルを特定し、規約『表示の安定』に沿って解消する。解消できない場合は、検出の対象から外す理由を記載する。

## 背景

[Issue #272](https://github.com/shuhei1101/dev-docs/issues/272) の要望。作業 PR [#265](https://github.com/shuhei1101/dev-docs/pull/265) のモックのレビューで、reviewer が対象外の逸脱として報告した（[報告](https://github.com/shuhei1101/dev-docs/pull/265#discussion_r4600035578)）。

`frontend/src/features/settings/settings/settings-screen.stories.tsx` のうちダイアログを開くストーリー（EditOutsideRead など）を `detect_screen_issues`（`target: story`）にかけると、1280x800 と 390x844 で 1 件ずつ検出され、検出には対象の要素が付かない。`frontend/src` には高さを動かす `transition` の記述が無く、同じ `layout-transition` を直した [#166](https://github.com/shuhei1101/dev-docs/issues/166)（共有の部品の `transition-all`）とは別の出典になる。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [画面](./画面.md) | 画面の計画書 |
