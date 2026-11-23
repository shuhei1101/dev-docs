# メタデータの画面の直コミットが衝突したとき、修正をブランチに残し、同じ文書の別の項目の変更とは衝突しないようにする

## 概要

利用者が、メタデータの画面の直コミットがほかの変更と衝突しても修正を失わず、手で解消せずに済む。
同じ文書の別の項目の変更とは衝突せずにコミットでき、dev-docs 自身の文書のメタデータも画面から直コミットできる。

## 背景

[Issue #314](https://github.com/shuhei1101/dev-docs/issues/314) の要望。
メタデータの画面（[#310](https://github.com/shuhei1101/dev-docs/issues/310)。作業 PR [#313](https://github.com/shuhei1101/dev-docs/pull/313)）の直コミットは、編集の間に同じ文書がほかの変更で書き換わると 409 で断られ、利用者が今の内容を確認して手でもう一度修正する。
照合は文書の全体のバージョンのため、別の人が概要を、利用者がタグを修正したときのように、同じ文書の別の項目でも衝突する。
dev-docs の `project-index.yaml` には `direct_commit` が無く、dev-docs 自身の文書のメタデータは画面から修正できない。

衝突の扱いは、話し合いで利用者が決めた（ふだんは今の直コミットのまま、衝突したときだけ project-index がブランチを作って修正を残し、端末の側のスクリプトを実行する）。

| Issue / PR | 内容 |
| --- | --- |
| [shuhei1101/project-index#263](https://github.com/shuhei1101/project-index/issues/263)（close 済み。作業 PR [shuhei1101/project-index#264](https://github.com/shuhei1101/project-index/pull/264)） | 書き込みの API の `baseCommit`・衝突したときのブランチ・衝突したときのスクリプトと、文書の取得の `itemVersions`（項目ごとのバージョン） |
| [#310](https://github.com/shuhei1101/dev-docs/issues/310)（close 済み。作業 PR [#313](https://github.com/shuhei1101/dev-docs/pull/313)） | メタデータの画面の本体 |

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [画面](./画面.mark.md) | 画面の計画書 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 開発ドキュメントサーバーの計画書 |
| [反映作業](./反映作業/index.yaml) | 反映作業の一覧 |
