# スキーマ駆動の変換が出す表のマーカーを mdmark の JSON の引数の記載へ移す

## 概要

スキーマ駆動の変換が出す表のマーカーを mdmark の JSON の引数の記載で出し、変換した文書を `mdmark check` にかけても `legacy_mark` が出ないようにする。

## 背景

[Issue #217](https://github.com/shuhei1101/dev-docs/issues/217) の要望。[#210](https://github.com/shuhei1101/dev-docs/pull/210) で mdmark を `v0.13.0` に上げた。
`v0.13.0` は前の記載方法（位置の値・`キー=値`・`+機能`）のマーカーをこのマイナーバージョンの間だけ読み込み、`mdmark check` が `legacy_mark` で返す。
変換（`src/dev_docs/features/convert/markdown.py`）が出す表のマーカーは前の記載方法のままのため、次のマイナーバージョンへ上げると表が描かれなくなる。

画面（`frontend/src/features/docs/doc-view/tables.ts`）は、変換が出したマーカーの `+columns` の有無で列の表示の保存先を決め、保存した隠す列を `hide=` でマーカーへ書き足している。
変換が出すマーカーを JSON に変えると、この読み書きも追従が要る。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [画面](./画面.md) | 画面の計画書 |
