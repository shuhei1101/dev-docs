# 外部ライブラリの設計書の使用箇所（used_in）の実在しないパスを削除・修正する

## 概要

外部ライブラリの設計書の使用箇所（`used_in`）を、develop に実在するパスだけにする。

## 背景

[Issue #184](https://github.com/shuhei1101/dev-docs/issues/184) の要望。[#182](https://github.com/shuhei1101/dev-docs/pull/182) の実装中に、外部ライブラリ『mdmark』（`docs/library/LIB-155-9.yaml`）の `used_in` が、[#163](https://github.com/shuhei1101/dev-docs/pull/163) で project-index へ移って develop に無い `src/dev_docs/integrations/mdmark.py` を指していることが分かった。
同じ設計書の `mdmark check --text` は `status: planned` のままだが、[#182](https://github.com/shuhei1101/dev-docs/pull/182) で入った結合テスト `tests/integration/server/test_get_document.py` が使用している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.md) | 画面の計画書 |
