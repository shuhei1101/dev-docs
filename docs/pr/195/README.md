# GitHub Pages で使用しなくなった Jekyll の設定・テーマ・分類のトップページを削除する

## 概要

GitHub Pages を mdmark の `build` に切り替えた後に使用しなくなった、Jekyll の設定・AI Monitor のテーマ・分類のトップページ・テーマの記録を削除する。

## 背景

[Issue #194](https://github.com/shuhei1101/dev-docs/issues/194) の要望。
[PR #192](https://github.com/shuhei1101/dev-docs/pull/192)（起点 Issue [#173](https://github.com/shuhei1101/dev-docs/issues/173)）で、Pages の公開ページを `.github/workflows/pages.yml` と `scripts/build_pages.py` が mdmark の `build` でまとめる 1 枚の HTML に切り替えた。
切り替えた後は、`docs/_config.yml`・`docs/_theme/`・`docs/guide/` の分類のトップページ・`ai-monitor-theme.yaml` を参照するものが無い。
AI Monitor v0.4.0 のテーマの取り込みは [#74](https://github.com/shuhei1101/dev-docs/issues/74) から移した範囲で、テーマを残すと決めた場合だけ実施する。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、配布物の受け取り方の未確定の論点 |
