# 文書の取得で配信元の文書の一覧を毎回取り直さず、文書の多い配信元の表示と差分を速くする

## 概要

利用者が、文書の多い配信元でも、文書と差分つきの文書を待たされずに開けるようにする。

## 背景

[Issue #301](https://github.com/shuhei1101/dev-docs/issues/301) の要望。
ai-monitor の文書を差分つきで開くと、本文が返るまで約 19 秒かかった（2026-11-20 10:23、`docs/data/DATA-3694-1.yaml`）。
内訳は、表示側のリビジョンの文書の一覧 約 3.8 秒・文書 1 件 約 7.8 秒・比較元のリビジョンの文書の一覧 約 4.4 秒・差分の作成と返却 約 2.3 秒だった。
develop の [src/dev_docs/features/view/document.py](https://github.com/shuhei1101/dev-docs/blob/7ef1589/src/dev_docs/features/view/document.py) の文書の取得は、文書を開くたびに project-index から値つきの文書の一覧（ai-monitor で約 20MB）を取り、差分のときは `_diff` が比較元のリビジョンの一覧も取る。
`src/dev_docs/` に文書の一覧を保持する実装と、応答を圧縮する実装は無く、文書 1 件の応答は約 744KB ある。
project-index 側の読み込みの遅さは [shuhei1101/project-index#85](https://github.com/shuhei1101/project-index/issues/85)（クローズ済み）・[shuhei1101/project-index#197](https://github.com/shuhei1101/project-index/issues/197) が扱う。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 開発ドキュメントサーバーの計画書 |
