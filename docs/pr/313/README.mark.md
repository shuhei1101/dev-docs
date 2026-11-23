# 配信元のメタデータを画面で一覧し、画面で溜めた修正をまとめて直コミットする

## 概要

利用者が、dev-docs の画面で配信元のメタデータ（用語集・エイリアス・タグ・rule-inject の索引・配信元の設定・管理用の YAML）を一覧で参照でき、画面で溜めた修正をまとめてコミット・プッシュできる。

## 背景

[Issue #310](https://github.com/shuhei1101/dev-docs/issues/310) の要望。
メタデータは各配信元の YAML のファイルにあり、利用者は何が登録されているか（用語が登録済みか・規約がどのパスに適用されているか）を画面で一覧できない。
修正には Issue と作業 PR を経るか、エージェントへの依頼が要り、気づいた所をその場でまとめて修正する方法が無い。

書き込みは、画面のサーバーから直コミットつきで書き込む project-index の書き込みの API を使用する。

| Issue / PR | 内容 |
| --- | --- |
| [shuhei1101/project-index#252](https://github.com/shuhei1101/project-index/issues/252)（close 済み。作業 PR [shuhei1101/project-index#256](https://github.com/shuhei1101/project-index/pull/256)） | 画面のサーバーから直コミットつきで文書を書き込める経路と、その呼び出しの許可の決め方 |
| [shuhei1101/project-index#209](https://github.com/shuhei1101/project-index/issues/209)（close 済み） | `write_docs` の `commit` による直コミット |

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [画面](./画面.mark.md) | 画面の計画書 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 開発ドキュメントサーバーの計画書 |
