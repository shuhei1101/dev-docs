# フォルダ構成の設計書を作成し、各設計書の notes に退避したフォルダのツリーを移す

## 概要

dev-docs のフォルダ構成を、knowledge のスキーマ `layout` のフォルダ構成の設計書 1 件で持ち、配信元 dev-docs から配信する。

## 背景

[Issue #258](https://github.com/shuhei1101/dev-docs/issues/258) の要望。
[#256](https://github.com/shuhei1101/dev-docs/pull/256)（起点 Issue [#224](https://github.com/shuhei1101/dev-docs/issues/224)）で設計書のスキーマを knowledge の `design-schemas` の参照へ移したとき、スキーマに無いキー（アーキテクチャ図の `repository.layout` と、モジュール構成の `directory`）のツリーを、各設計書の `notes` の「フォルダ構成」のセクションへ暫定で移した。
develop（[49fa597](https://github.com/shuhei1101/dev-docs/commit/49fa597)）では、アーキテクチャ図とモジュール構成 19 件が「フォルダ構成」のセクションを持ち、`docs/layout/` は無い。
AI Monitor の変換 `schemas/conversions/v0.4.0.py` の `_move_layout` は同じ移し方を持つが、`docs/module/` の設計書を改名する不具合（[shuhei1101/ai-monitor#3357](https://github.com/shuhei1101/ai-monitor/issues/3357)）を持つため使用しない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | フォルダ構成の設計書・`project-index.yaml`・アーキテクチャ図と、開発ドキュメントサーバー・開発用のスクリプトのモジュール構成の計画書 |
| [画面](./画面.md) | 画面のモジュール構成の計画書 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインのモジュール構成の計画書 |
