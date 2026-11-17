# 設計書の名前・ガイドのファイル名・コードのコメントに残る AI slop の単語を改名する

## 概要

シナリオ名・項目名・ガイドのファイル名・docstring が指す設計書の項目名に残る AI slop の単語を、AI slop の単語の対応表の置き換え先で改名し、対になる参照・リンク・docstring を同じ名前に合わせる。

## 背景

[Issue #253](https://github.com/shuhei1101/dev-docs/issues/253) の要望。
[PR #248](https://github.com/shuhei1101/dev-docs/pull/248)（起点 [Issue #95](https://github.com/shuhei1101/dev-docs/issues/95)）で `docs/` の AI slop を修正したが、名前は対になるテスト・リンク・コードとずれるため変えず、スコープ外から切り出した。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの設計書と docstring の計画書 |
