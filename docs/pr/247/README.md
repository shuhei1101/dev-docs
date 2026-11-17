# #212 の反映作業「端末の設定の移し替え」「dev-docs のサーバーの再起動」のスクリプトが持つ develop の worktree のパスを、今の作業場所に合わせる

## 概要

tester が #212 の反映作業「端末の設定の移し替え」「dev-docs のサーバーの再起動」を、今の作業場所の develop の worktree で実行できるようになる。

## 背景

[Issue #246](https://github.com/shuhei1101/dev-docs/issues/246) の不具合。
[作業 PR #212](https://github.com/shuhei1101/dev-docs/pull/212) の反映作業「端末の設定の移し替え」を tester がマージの後に実行したところ、dry-run の前提確認で止まった（[tester の報告](https://github.com/shuhei1101/dev-docs/issues/209#issuecomment-6935910586)）。
2 件の反映作業のスクリプトが、develop の worktree を移動前の `/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop` の固定値で持っている。
[起点 Issue #209](https://github.com/shuhei1101/dev-docs/issues/209) の close は、この修正と反映作業の実行を待って止まっている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
