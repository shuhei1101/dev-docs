# 画面の全体のスタイル（index.css・preflight-outside-mdmark.css）を frontend/src/shared/styles/ へ移す

## 概要

画面の全体のスタイル `frontend/src/index.css` と、それが読み込む `preflight-outside-mdmark.css` を、knowledge の規約『Tailwind』『フォルダ構成』のとおり `frontend/src/shared/styles/` へ移す。

## 背景

[Issue #293](https://github.com/shuhei1101/dev-docs/issues/293) の要望。
作業 PR [#291](https://github.com/shuhei1101/dev-docs/pull/291)（起点 Issue [#290](https://github.com/shuhei1101/dev-docs/issues/290)）で `LAY-275-1` の `frontend/src/` を `convention: react-core-folder-structure` にしたレビューで、reviewer が対象外の逸脱として報告した。
規約はトークン・要素の既定と `@theme inline` の配置先を `shared/styles/` と定めるが、develop では `frontend/src/` の直下にあり、`shared/styles/` が無い。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [画面](./画面.md) | スタイルの移動と、パスを持つ箇所の追随の計画書 |
