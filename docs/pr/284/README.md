# tmp/ の PNG を Git の管理から除外し、使用されていない docs/generated/ の記載を整理する

## 概要

`tmp/screenshots/review-56/` の PNG を Git の管理から除外して `tmp/` を commit しないようにし、使用されていない `docs/generated/` を前提にする記載を削除する。

## 背景

[#282](https://github.com/shuhei1101/dev-docs/issues/282) の要望で、同じ種類の [#271](https://github.com/shuhei1101/dev-docs/issues/271) と [#279](https://github.com/shuhei1101/dev-docs/issues/279) を 1 つの作業 PR で対応する。

- [#271](https://github.com/shuhei1101/dev-docs/issues/271): [#56](https://github.com/shuhei1101/dev-docs/pull/56) のレビューのスクリーンショットが Git の管理に入っており、規約『作業ディレクトリ』の一時ファイルの配置先と食い違う。[#270](https://github.com/shuhei1101/dev-docs/pull/270) のレビューで見つかった
- [#279](https://github.com/shuhei1101/dev-docs/issues/279): `docs/generated/` へ出力するコマンド・コードが無いのに、`.gitignore`・フォルダ構成の設計書・公開ページのビルドに前提にする記載が残る。[#275](https://github.com/shuhei1101/dev-docs/pull/275) のレビューで見つかった

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |

変更が及ぶ設計書（フォルダ構成・開発用のスクリプトのモジュール構成）と実装は、アーキテクチャ図のサブシステムに属さないため、対象システムの計画書を作らない。
