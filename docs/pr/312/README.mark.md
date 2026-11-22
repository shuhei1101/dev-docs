# iPad で表の見出し行を上端に隠れる時にだけ固定する

## 概要

利用者が iPad で dev-docs の文書を参照するとき、本文の表の見出し行が、画面の上端に隠れる時にだけ固定され、位置がずれない。

## 背景

[Issue #311](https://github.com/shuhei1101/dev-docs/issues/311) の要望。
iPad で dev-docs の画面を開くと、本文の表の見出し行が、スクロールで上端に隠れる前（画面の半分ほどの位置）に固定され、位置が下にずれる。
同じ表を MindStella のプレビューで開くと、見出し行は上端に隠れる時に固定され、ずれない。表はどちらも mdmark で描いている。

関連する Issue / PR は次のとおり。

| Issue / PR | 内容 |
| --- | --- |
| [shuhei1101/mindstella#614](https://github.com/shuhei1101/mindstella/issues/614) | プレビューの表の見出し行の固定 |
| [shuhei1101/mdmark#683](https://github.com/shuhei1101/mdmark/issues/683)（close 済み。作業 PR [shuhei1101/mdmark#705](https://github.com/shuhei1101/mdmark/pull/705)） | 見出し行を留める処理が `timeline` と `script` で留まる位置が違う |

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.mark.md) | 画面の計画書 |
