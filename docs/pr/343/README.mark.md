# 文書の画面の列の表示のメニューを mdmark の表のメニューから開くテーブル設定に合わせる

## 概要

文書の画面の結合テストの「列の表示のメニュー」と画面設計『文書の画面』の `列の表示のメニュー` を、mdmark の develop の表のメニューから開くテーブル設定に合わせ、結合テストが pass するようにする。

## 背景

[Issue #342](https://github.com/shuhei1101/dev-docs/issues/342) の不具合。
画面は mdmark を jsDelivr の `develop` から読み込み、mdmark の develop では [shuhei1101/mdmark#811](https://github.com/shuhei1101/mdmark/pull/811)（[0413662](https://github.com/shuhei1101/mdmark/commit/04136622)）で表の上の `テーブル設定` のボタンが、見出し行の右上の「表のメニュー」のボタンで開くメニューの項目に移った。
そのため `tests/integration/frontend/doc-view-screen.spec.ts` の `列の表示のメニュー` のテストが `getByRole('button', { name: 'テーブル設定' })` を見つけられず fail する。
[#340](https://github.com/shuhei1101/dev-docs/pull/340) の結合テスト作成で見つかった。
同じテストは [#157](https://github.com/shuhei1101/dev-docs/issues/157) で mdmark v0.10.0 のボタン名に合わせている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.mark.md) | 画面の計画書 |
