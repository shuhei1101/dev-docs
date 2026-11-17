# フォルダ構成の設計書 LAY-275-1 を実態とスキーマに合わせる

## 概要

フォルダ構成の設計書 `LAY-275-1` を、リポジトリの実態と `layout` のスキーマの `x-rules` に合わせる。生成物の管理方針・`migrations` の下のエントリ・`src/dev_docs/` と `frontend/src/` の記載の構造を統一する。

## 背景

[Issue #290](https://github.com/shuhei1101/dev-docs/issues/290) の要望で、[#276](https://github.com/shuhei1101/dev-docs/issues/276)・[#277](https://github.com/shuhei1101/dev-docs/issues/277)・[#278](https://github.com/shuhei1101/dev-docs/issues/278) をまとめて対応する。
3 件とも、作業 PR [#275](https://github.com/shuhei1101/dev-docs/pull/275)（起点 Issue [#258](https://github.com/shuhei1101/dev-docs/issues/258)）でフォルダのツリーを `LAY-275-1` へ移したときに見つかり、スコープ外として切り出したもの。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理・決定した内容・変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | `src/dev_docs/` のエントリの計画書 |
| [画面](./画面.md) | `frontend/src/` のエントリと生成物の計画書 |
