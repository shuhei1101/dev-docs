# dev-docs の画面のサーバーの project-index の付け替え口を、モックから本物の project-index の API へつなぐ

## 概要

dev-docs の画面のサーバーが、本物の project-index の読み取り API と端末の設定の API から文書・検索・リビジョン・配信元の状態を取得し、端末の設定を保存できるようにする。

## 背景

[Issue #164](https://github.com/shuhei1101/dev-docs/issues/164) の要望。
[#163](https://github.com/shuhei1101/dev-docs/pull/163)（起点 [#114](https://github.com/shuhei1101/dev-docs/issues/114)）で、画面のサーバーは project-index を付け替え口で呼ぶ構造になったが、付け替え口は [shuhei1101/project-index#14](https://github.com/shuhei1101/project-index/issues/14) に記載した入出力に沿ったモックで作られている。
project-index#14 は [shuhei1101/project-index#15](https://github.com/shuhei1101/project-index/pull/15) で実装されたが、入出力がモックの契約と異なり（[docs/external-api/API-155-1.yaml](https://github.com/shuhei1101/dev-docs/blob/develop/docs/external-api/API-155-1.yaml) の `verification.detail`）、稼働中の dev-docs のサーバーの再起動と端末の設定の移し替えは #163 から持ち越されている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
