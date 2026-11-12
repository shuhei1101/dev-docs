# アーキテクチャ図 ARCH-155-1 のデータの図の辺から `line: reply` を削除する

## 概要

アーキテクチャ図 `ARCH-155-1` の `overview` のデータの図の辺 2 つから、AI Monitor v0.4.0 の設計書のスキーマで無くなった `line: reply` を削除する。

## 背景

[#161](https://github.com/shuhei1101/dev-docs/issues/161) の要望。
[shuhei1101/ai-monitor#3104](https://github.com/shuhei1101/ai-monitor/issues/3104) で設計書のスキーマのデータの図のキーが変わり、[shuhei1101/ai-monitor#3273](https://github.com/shuhei1101/ai-monitor/issues/3273) で v0.4.0 の変換を dev-docs の `origin/develop` に適用して確認したところ、変換の対象はこの 2 行だけだった。
変換の `convert` は `docs/module/MOD-155-*.yaml` を改名してしまうため使用せず、手で削除する。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
