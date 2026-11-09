# convert

スキーマ駆動か `converters[]` による文書の Markdown への変換

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [types.py](./types.py.yaml) | 変換の結果・失敗・表し方・図の種類・図の中間データ・描画の文脈の型 |
| [service.py](./service.py.yaml) | 変換の選択・`converters[]` の実行・結果の控え |
| [diagrams.py](./diagrams.py.yaml) | `x-diagram` の値と手で書く Mermaid の、mdmark の図の部品か Mermaid への描画 |
| [flow_layout.py](./flow_layout.py.yaml) | フロー図の中間データの、mdmark のフロー図の部品の定義への配置 |
| [mermaid.py](./mermaid.py.yaml) | 手で書く Mermaid の `flowchart`・`sequenceDiagram` の読み取り |
| [inline.py](./inline.py.yaml) | 文字列の値の中の、図・ファイルツリー・手順・参照・Issue 番号・値の選択肢の書き換え |
| [embed.py](./embed.py.yaml) | 埋め込みのマーカーの表への展開 |
| [decisions.py](./decisions.py.yaml) | `decisions.folders` からの、設計書の `decisions` の検討事項の文書の検索 |
| [markdown.py](./markdown.py.yaml) | スキーマ駆動の文書の Markdown への変換と表の描画 |

<!-- /table -->
