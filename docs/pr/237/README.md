# 文書のマーカーを mdmark の JSON の記載へ移す

## 概要

`docs/` の Markdown の今の書き方（`キー=値`・位置の値）のマーカーを、mdmark の JSON の記載へ移す。

## 背景

[#193](https://github.com/shuhei1101/dev-docs/issues/193) の要望。
mdmark は [shuhei1101/mdmark#477](https://github.com/shuhei1101/mdmark/pull/477) でマーカーの設定を JSON のオブジェクトで記載できるようにし、今の書き方を読む処理を [shuhei1101/mdmark#479](https://github.com/shuhei1101/mdmark/issues/479) で削除する。
削除された版を読むと、今の書き方のマーカーは設定が当たらなくなる。

画面は [#127](https://github.com/shuhei1101/dev-docs/issues/127) で develop のタグの mdmark を読むようになり、今の develop は `mdmark@v0.13.0` を読む（JSON の記載を描ける）。
今の書き方のマーカーは `docs/` の Markdown 68 ファイルにあり、全て `<!-- table: data -->` である。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と移行の方法 |
