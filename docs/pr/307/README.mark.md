# エラーのアラートの説明文・一覧・ボタンの文字色を、背景とのコントラストの基準を満たす色にする

## 概要

文書の画面の「変換の失敗」のアラートの説明文・一覧・`再読み込み` のボタンの文字色を、axe の `color-contrast` の基準を満たす色にする。

## 背景

[Issue #305](https://github.com/shuhei1101/dev-docs/issues/305) の不具合。
作業 PR [#304](https://github.com/shuhei1101/dev-docs/pull/304) のモック作成で、reviewer が対象外の逸脱として報告した。
アラートは shadcn の `Alert` の `destructive` の variant で描いており、説明文（`AlertDescription`）の文字色は `--destructive` を 90% の不透明度で重ねた色になっている。
同じ variant は、設定画面の配信元のダイアログ・削除の確認のダイアログと、共通の project-index から受け取れなかったことの警告でも使用している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と影響する UC 一覧 |
| [画面](./画面.mark.md) | 画面の計画書 |
