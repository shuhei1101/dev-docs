# dev-docs のサーバーの再起動の待ちと反映作業の判定を、execv で同じプロセスのまま起動し直した後にも新しいサーバーを見分けられるようにする

## 概要

反映作業『dev-docs のサーバーの再起動』の待ちと判定が、`os.execv` で同じプロセスのまま起動し直したサーバーを新しいサーバーとして見分け、再起動できたときに `ok` を返却するようにする。

## 背景

[#137](https://github.com/shuhei1101/dev-docs/issues/137) の要望。
[PR #130](https://github.com/shuhei1101/dev-docs/pull/130) のマージの後の反映作業『dev-docs のサーバーの再起動』を tester が 2 回流し、2 回とも実行の工程で `新しいサーバーの待ち受け: failed` で止まった（[#129 の報告](https://github.com/shuhei1101/dev-docs/issues/129#issuecomment-6729946259)）。
サーバーのログでは 2 回とも再起動できていた。
[PR #125](https://github.com/shuhei1101/dev-docs/pull/125) で配置した `scripts/dev-docs-server-wait.sh` の `listening` は、待ち受けるプロセスの `ps -o lstart=` の起動時刻で新しいサーバーを判定する。再起動は `os.execv` で同じプロセスを置き換えるため、PID も起動時刻も変わらない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
