# テスト実行方法の層ごとに実行場所を決め、ランナーで回せる層を GitHub Actions の workflow で回す

## 概要

開発者とエージェントが、テスト実行方法の層のうちランナーで回せる層を GitHub Actions のランナーで回せるようになる。
ランナーで回せないときは、手元の全件実行・個別実行で回せる。

## 背景

[Issue #198](https://github.com/shuhei1101/dev-docs/issues/198) の要望。
全てのプロジェクトの単体・結合テストが同じ WSL の上で回り、手元のメモリが足りない。
[テスト実行方法](https://github.com/shuhei1101/dev-docs/blob/38c8128/docs/test-procedure/TP-155-1.yaml) の全ての層が手元で回る前提で記載されていて、層ごとの実行場所が決定していない。
テストを回す workflow も無い（`.github/workflows/` は GitHub Pages への配信の workflow だけ）。

前提の [shuhei1101/knowledge#350](https://github.com/shuhei1101/knowledge/issues/350)（判定フローチャート『テストの実行場所』とテンプレート『テスト実行方法』）・[shuhei1101/knowledge#351](https://github.com/shuhei1101/knowledge/issues/351)（workflow のインターフェース定義）・[shuhei1101/ai-monitor#3434](https://github.com/shuhei1101/ai-monitor/issues/3434)（runner の層をランナーで回す仕組み）は全て close している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーのテストの実行場所と、テストを回す workflow・lint の計画書 |
| [画面](./画面.md) | 画面のテストの実行場所の計画書 |
