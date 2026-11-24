# 文書の画面の表の既定のピン止めを mdmark の既定（描いた直後はどの列も留めない）に合わせる

## 概要

利用者が文書の画面で表を開いたとき、描いた直後のピン止めの列が mdmark の既定と同じになる。

## 背景

[Issue #324（画面の Markdown の表の既定のピン止めを、mdmark の既定に合わせる）](https://github.com/shuhei1101/dev-docs/issues/324) の要望。
[shuhei1101/mdmark#735](https://github.com/shuhei1101/mdmark/pull/735) で表の既定のピン止めが「描いた直後はどの列も留めない」に変わり、`table.pin_default` で以前の動き（先頭の列を留める）を選べるようになった。
MindStella の画面では、利用者の判断で mdmark の既定のままにした（[shuhei1101/mindstella#639](https://github.com/shuhei1101/mindstella/issues/639)・[shuhei1101/mindstella#682](https://github.com/shuhei1101/mindstella/issues/682)）。

文書の画面は jsDelivr から端末の設定の `mdmark_version`（既定は `develop`）の mdmark を読み込み、`mount` に `table.pin_default` を指定していないため、既に mdmark の既定で描いている。
画面設計『文書の画面』は、表の既定のピン止めを記載していない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [画面](./画面.mark.md) | 画面の計画書 |
