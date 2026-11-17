# 常駐サーバーの再起動のコマンドから呼ぶ、依存の定義が変わっていれば依存を入れ直してから dev-docs.service を起動し直すスクリプトを追加する

## 概要

AI Monitor が、develop が進んだときに dev-docs の常駐サーバーを、依存を `uv.lock` どおりにそろえてから起動し直せるようになる。

## 背景

[Issue #242](https://github.com/shuhei1101/dev-docs/issues/242) の要望。
AI Monitor は `projects[].resident_servers` の `restart_command` で常駐サーバーを起動し直し、dev-docs の今のコマンドは `systemctl --user restart dev-docs.service` で依存を入れ直さない。
依存の定義を変える PR が develop に入ると、作業ツリーのコードと `.venv` が食い違ったまま起動し直す。
同じ食い違いで claude-balancer のコマンドが `ModuleNotFoundError` で落ち、全プロジェクトのエージェントの起動が止まった（[shuhei1101/ai-monitor#3521](https://github.com/shuhei1101/ai-monitor/issues/3521)）。
`restart_command` をこのスクリプトへ差し替えるのは AI Monitor 側の [shuhei1101/ai-monitor#3533](https://github.com/shuhei1101/ai-monitor/pull/3533) で、同じ構造の先例は [shuhei1101/claude-balancer#312](https://github.com/shuhei1101/claude-balancer/pull/312) の `bin/restart-resident`。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 常駐サーバーを起動し直すスクリプトの計画書 |
