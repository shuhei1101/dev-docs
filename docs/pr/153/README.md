# #131 の反映作業のスクリプトが管理の MCP の status を待つ秒数を応答時間に合わせ、空の応答を打ち切りの理由つきの失敗にする

## 概要

#131 の反映作業『dev-docs のサーバーの再起動』のスクリプトが、管理の MCP の `status` の応答を待ちきり、応答が空か打ち切られたときは打ち切った旨と秒数を理由に出して失敗する。

## 背景

[#146](https://github.com/shuhei1101/dev-docs/issues/146) の要望。
[PR #131](https://github.com/shuhei1101/dev-docs/pull/131) のマージの後の反映作業『dev-docs のサーバーの再起動』が、確認の工程で `端末の設定のパス: failed` で止まった（[#112 の tester の報告](https://github.com/shuhei1101/dev-docs/issues/112#issuecomment-6733357448)）。
管理の MCP の `status` の応答に約 119 秒かかり、スクリプトの `curl --max-time 60` が打ち切られて空の応答になっていた。サーバーの反映は有効になっていた。
`実行.sh` も同じ打ち切りで、空の応答を `再起動の前の配信元: ok（0 件）` と記録していた。
`status` 自体の遅さは [#126](https://github.com/shuhei1101/dev-docs/issues/126)（[PR #136](https://github.com/shuhei1101/dev-docs/pull/136)）が扱う。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
