# dev-docs migrate が project-index の端末の設定の書き込みの応答を 45 秒で打ち切って途中で止まる不具合を修正する

## 概要

利用者が `dev-docs migrate --project-index` で端末の設定の `sources` を project-index へ移すとき、project-index の書き込みの応答が 45 秒を超えても移し替えを最後まで終えられ、途中で失敗しても dev-docs と project-index の端末の設定が食い違ったまま残らないようにする。

## 背景

[Issue #197](https://github.com/shuhei1101/dev-docs/issues/197) の不具合。
[#164](https://github.com/shuhei1101/dev-docs/issues/164)（作業 PR [#183](https://github.com/shuhei1101/dev-docs/pull/183)）の反映作業「端末の設定の移し替え」を tester が 2 回実行し、2 回とも `dev-docs migrate` が project-index の `/settings/sources` への書き込みの応答を `PROJECT_INDEX_TIMEOUT_SEC` の 45 秒以内に受けられずに止まった（[tester の報告](https://github.com/shuhei1101/dev-docs/issues/164#issuecomment-6852521549)）。
project-index には配信元の行が書き込まれ、dev-docs の端末の設定は移されないまま残った。
project-index は書き込みの後に配信元を同期で読み直し（[shuhei1101/project-index#25](https://github.com/shuhei1101/project-index/pull/25)）、書き戻しの PUT の応答も 44.8 秒・45.1 秒かかった。
同じ報告で、#183 の反映作業の `切り戻し.sh` が `yaml` の無い Python を使用することと、別 PR の控えを書き戻してしまうことも見つかった。
#164 の反映作業「端末の設定の移し替え」「dev-docs のサーバーの再起動」は、この修正を待っている（[#164 の確認](https://github.com/shuhei1101/dev-docs/issues/164#issuecomment-6852784537)）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
