# 文書の画面の独自の目次を削除し、mdmark の標準の目次を使う

## 概要

利用者が、文書の画面で mdmark の標準の目次だけを使用して本文を読めるようになる（目次が 2 つ並ばない）。

## 背景

[Issue #88](https://github.com/shuhei1101/dev-docs/issues/88) の要望。
文書の画面は本文の右に独自の目次（`DocToc`）を置いているが、mdmark が描く本文にも標準で右側の目次（`.mdmark-side-toc`）が出るようになり、目次が 2 つ並んで本文の幅を狭めている。
比較元からの変更箇所の強調は [#44](https://github.com/shuhei1101/dev-docs/issues/44) で mdmark の差分の強調（[mdmark#222](https://github.com/shuhei1101/mdmark/issues/222)）を画面につないだ。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [画面](./画面.md) | 画面の計画書 |
