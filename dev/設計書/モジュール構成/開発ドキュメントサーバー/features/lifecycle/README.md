# lifecycle

再起動の制御とクローンの更新

## 目次

| ページ | 概要 |
| --- | --- |
| [types.py](./types.py.yaml) | 再起動・更新の結果と定数 |
| [control.py](./control.py.yaml) | 再起動の要求と uvicorn の停止 |
| [update.py](./update.py.yaml) | `git pull --ff-only`・`uv sync` によるクローンの更新 |
