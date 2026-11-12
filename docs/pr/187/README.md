# 画面が読む mdmark を mdmark@master から develop に打ったタグへ切り替える

## 概要

文書の画面が jsDelivr から読み込む mdmark を、`mdmark@master` から mdmark の develop に打ったタグへ切り替える。

## 背景

[Issue #127](https://github.com/shuhei1101/dev-docs/issues/127) の要望。
mdmark は 0.x の間 release を切らずに develop だけで開発し、スプリントの区切りに develop の commit へタグを打つ（[shuhei1101/mdmark#434](https://github.com/shuhei1101/mdmark/issues/434)）。
画面の `use-mdmark.ts` が参照する `mdmark@master` は、0.x の間は更新されない。
切り替える先のタグは、判定のノードの種類（[shuhei1101/mdmark#268](https://github.com/shuhei1101/mdmark/pull/268)）と ER 図の部品（[shuhei1101/mdmark#298](https://github.com/shuhei1101/mdmark/pull/298)）を含むものにする（[#118](https://github.com/shuhei1101/dev-docs/issues/118) から移した範囲）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [画面](./画面.md) | 画面の計画書 |
