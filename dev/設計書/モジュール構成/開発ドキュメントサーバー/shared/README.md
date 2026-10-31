# shared

例外の階層・YAML の読み書き・ファイルの置き換え・ハッシュ・パスの照合・API の DTO の基底・スキーマの違反・動いているバージョン

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [api_model.py](./api_model.py.yaml) | 画面の API の DTO の基底（キーは camelCase） |
| [errors.py](./errors.py.yaml) | `DevDocsError` と、MCP・画面が返すエラーの階層 |
| [files.py](./files.py.yaml) | 一時ファイルからのファイルの置き換え |
| [hashing.py](./hashing.py.yaml) | 内容のハッシュ（文書のバージョン） |
| [paths.py](./paths.py.yaml) | 作業場所の glob の照合とパスの正規化 |
| [schema_check.py](./schema_check.py.yaml) | JSON Schema の違反を項目のパスつきの `Violation` にする |
| [version.py](./version.py.yaml) | 動いているプロセスが起動した時点の dev-docs のバージョン |
| [yaml_io.py](./yaml_io.py.yaml) | YAML の読み込みと、往復編集の読み書き |

<!-- /table -->
