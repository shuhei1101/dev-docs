# #210 の反映作業「dev-docs のサーバーの再起動」の確認スクリプトが、文書の取得を HTTP 200 で本文を返すまで上限つきで待ち、失敗時に HTTP の状態と応答の先頭を出す

## 概要

tester が #210 の反映作業「dev-docs のサーバーの再起動」の確認を、再起動の直後の一時的な応答で止まらずに実行できるようになる。

## 背景

[Issue #218](https://github.com/shuhei1101/dev-docs/issues/218) の不具合。
[作業 PR #210](https://github.com/shuhei1101/dev-docs/pull/210) の反映作業「dev-docs のサーバーの再起動」で、tester の実行が工程『確認』で止まった（[tester の報告](https://github.com/shuhei1101/dev-docs/issues/205#issuecomment-6884083576)）。
確認の直後に同じ文書を取り直すと HTTP 200 で `<!-- map: ` を含む本文が返却され、再起動と変換は有効だった。
確認スクリプトが、再起動の直後の文書の取得を 1 回だけ・HTTP の状態を確認せずに判定している。
[起点 Issue #205](https://github.com/shuhei1101/dev-docs/issues/205) の反映作業は、この修正を待って止まっている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
