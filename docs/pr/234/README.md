# dev-docs serve を起動し直したら起動し直す前のプロセスを残さず、ポートを持つプロセスを 1 つにする

## 概要

利用者と AI Monitor が `dev-docs serve` を起動し直したら、起動し直したプロセスが配信を引き継ぎ、ポートを持つプロセスが 1 つになる。

## 背景

[Issue #233](https://github.com/shuhei1101/dev-docs/issues/233) の不具合。
[Issue #225](https://github.com/shuhei1101/dev-docs/issues/225) の作業 PR [#230](https://github.com/shuhei1101/dev-docs/pull/230) の計測の間に `dev-docs serve` のプロセスが 2 つ見つかり、#230 のスコープ外から切り出した。

2026-11-16 03:14（JST）の時点で、この端末の状態は次のとおり。

| 対象 | 状態 |
| --- | --- |
| pid 71352 | `127.0.0.1:8781` で待ち受けている。親が pid 1 で、cgroup が tmux の scope（`app-tmux.slice`）。systemd の unit の外で、セッション開始のフックが切り離して起動したプロセス |
| `dev-docs.service`（systemd --user） | `Restart=on-failure`。起動のたびにポートの使用中（終了コード 3）で終わり、restart counter が 5090 まで増えている（1 回あたり CPU 約 1.6 秒） |
| AI Monitor の常駐サーバーの設定 | `restart_command: systemctl --user restart dev-docs.service`。unit のプロセスだけを起動し直すため、71352 は止まらない |

`dev-docs.log` の 2026-11-15 07:15:09 には、2 つのプロセス（71517・71352）が同時に起動し、片方が `Errno 98` で終わった記録がある。
unit を起動し直す間にポートが空き、セッション開始のフックが unit の外で起動したプロセスが待ち受けを取った。
以降、develop が進んでも 71352 は 2026-11-15 に読み込んだコードのまま配信している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | `dev-docs serve` の起動・再起動の計画書 |
| [管理用プラグイン](./管理用プラグイン.md) | セッション開始のフックと global-setup の計画書 |
| [反映作業](./反映作業/index.yaml) | マージの後に、unit の外で動いているプロセスを止めて unit へ引き継がせる作業 |
