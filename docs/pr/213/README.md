# 外部ライブラリ『mdmark』の使用箇所に scripts/build_pages.py と mdmark build のコマンドを追加する

## 概要

外部ライブラリ『mdmark』の設計書に、公開ページをまとめる `scripts/build_pages.py` と、そこで使用する `mdmark build` のコマンドを記載する。

## 背景

[Issue #207](https://github.com/shuhei1101/dev-docs/issues/207) の要望。
作業 PR [#204](https://github.com/shuhei1101/dev-docs/pull/204)（起点 [#184](https://github.com/shuhei1101/dev-docs/issues/184)）の現状調査で、[scripts/build_pages.py](https://github.com/shuhei1101/dev-docs/blob/8c99253eaac31c283e7f87495bfde09b3267772c/scripts/build_pages.py) の `run_mdmark` が `npx` で mdmark の `build` を実行しているのに、設計書 [docs/library/LIB-155-9.yaml](https://github.com/shuhei1101/dev-docs/blob/8c99253eaac31c283e7f87495bfde09b3267772c/docs/library/LIB-155-9.yaml) の `used_in` に `scripts/build_pages.py` が無く、`catalogs` の `コマンド` が `mdmark check --text` だけだと分かった。
#204 は develop へマージ済み。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |

変更は外部ライブラリの設計書だけで、`scripts/` はアーキテクチャ図のサブシステムに属さないため、対象システムの計画書は配置しない。
