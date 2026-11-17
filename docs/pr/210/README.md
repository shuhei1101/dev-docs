# 設定画面が端末の設定の内容のバージョンを保存に添えて outsideRead を表示・変更し、ER図・状態遷移の設計書を mdmark の map で描く

## 概要

利用者が、設定画面でほかのプロセスの書き換えを上書きせずに配信元を保存でき、配信元の行の `outsideRead` を表示・変更できるようになる。
利用者が、ER図・状態遷移の設計書を、mdmark の map でテーブルの強調や遷移の再生などの操作つきの図として参照できるようになる。

## 背景

[Issue #205](https://github.com/shuhei1101/dev-docs/issues/205) は、[#190](https://github.com/shuhei1101/dev-docs/issues/190) と [#201](https://github.com/shuhei1101/dev-docs/issues/201) をまとめた親の Issue。

- #190: [shuhei1101/project-index#29](https://github.com/shuhei1101/project-index/pull/29) で、端末の設定の API が内容のバージョン（`version`）を返却し、`expectedVersion` が今のバージョンと違う書き換えを 409 で断るようになった。設定画面はバージョンを送信しないため、丸ごとの保存が、ほかのプロセス（MindStella など）が 1 行ずつ書き換えた行を気づかずに上書きする。取得の応答の `outsideRead` も画面に出ていない
- #201: [shuhei1101/mdmark#465](https://github.com/shuhei1101/mdmark/issues/465) で mdmark の map が ER 図・状態遷移図を描けるようになり、`v0.13.0` に入った。[shuhei1101/knowledge#363](https://github.com/shuhei1101/knowledge/issues/363)（作業 PR [shuhei1101/knowledge#366](https://github.com/shuhei1101/knowledge/pull/366)）で、ER図・状態遷移の設計書から Mermaid の `erDiagram`・`stateDiagram-v2` を生成するのは描く側（dev-docs）と決まった。今の dev-docs は ER 図を mdmark の ER 図の部品（`<!-- er -->`）、状態遷移をフロー図の部品（`<!-- flow -->`）で描いている

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [画面](./画面.md) | 画面の計画書 |
