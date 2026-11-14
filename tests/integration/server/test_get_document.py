from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from dev_docs.shared.yaml_io import load_yaml

from .conftest import REPO_ROOT, IndexSource, MockIndex, RealIndex, ServerEnv, doc, row

TABLE_DATA = {
    "id": "doc-1",
    "name": "文書 1",
    "items": [
        {"key": "k1", "label": "名称 1", "notes": "備考 1"},
        {"key": "k2", "label": "名称 2", "notes": "備考 2"},
    ],
}
NAV = {
    "tabs": [
        {"title": "規約", "items": [{"auto": {"document": "sample"}}]},
        {"title": "補足", "items": [{"page": "sample/doc-2"}]},
    ]
}
UPDATED = "2026-10-26T14:40:00+09:00"
DRAWN_SCHEMA = """\
type: object
title: 図の文書
properties:
  id: {type: string, title: ID}
  title: {type: string, title: タイトル}
  lead: {type: string, title: リード}
  internal_note: {type: string, title: 内部メモ, x-hidden: true}
  flow:
    title: 処理の流れ
    x-heading: 処理の流れ
    x-shape: diagram
    x-diagram: flowchart
    properties:
      nodes:
        type: array
        items:
          properties: {id: {title: ID}, label: {title: 表示}, kind: {title: 種類}, hint: {title: 補足}}
      edges:
        type: array
        items:
          properties:
            {from: {title: 元}, to: {title: 先}, label: {title: ラベル}, line: {title: 線}, tip: {title: 詳細}}
  states:
    title: 状態
    x-heading: 状態
    x-shape: diagram
    x-diagram: state
  sequence: {type: string, title: やり取り, x-heading: やり取り}
  chart: {type: string, title: 手順の図, x-heading: 手順の図}
  spec:
    type: object
    title: 仕様
    x-heading: 仕様
    properties: {kind: {title: 種類}, limit: {title: 上限}, owner: {title: 担当}}
  command: {type: string, title: 全件実行}
  items:
    title: 一覧
    x-heading: 一覧
    x-shape: table
    items:
      properties: {name: {title: 名前}, description: {title: 説明}}
"""
DRAWN_DOC = """\
id: doc-6
title: 図の文書 6
lead: 図と表で読む文書
internal_note: 内部メモの値
flow:
  nodes:
    - {id: q, label: 保存するか, kind: question, hint: 保存の判定}
    - {id: r, label: 保存する, kind: result}
  edges:
    - {from: q, to: r, label: YES, line: read, tip: 保存の判定の詳細}
  frame: {label: 判定, nodes: [q, r]}
states:
  initial: 下書き
  final: [公開]
  states: [{name: 下書き}, {name: 公開}]
  transitions:
    - {from: 下書き, to: 公開, trigger: 公開する}
sequence: |-
  ```mermaid
  sequenceDiagram
    participant U as 利用者
    U->>S: 開く
    S-->>U: 本文
  ```
chart: |-
  ```mermaid
  flowchart LR
    a[受付] --> b[(保存)]
  ```
spec: {kind: 定期, limit: 3, owner: 運用}
command: |-
  ```bash
  uv run pytest
  ```
items:
  - {name: 項目 1, description: 説明 1}
"""
UNREADABLE_SEQUENCE = "sequenceDiagram\n  A->>B: 読む\n  これは Mermaid の構文でない行"
UNREADABLE_DOC = (
    "id: doc-7\ntitle: 図の文書 7\nsequence: |-\n  ```mermaid\n"
    + "".join(f"  {line}\n" for line in UNREADABLE_SEQUENCE.splitlines())
    + "  ```\n"
)
UNREADABLE_DOC = (
    "id: doc-7\ntitle: 図の文書 7\nsequence: |-\n  ```mermaid\n"
    + "".join(f"  {line}\n" for line in UNREADABLE_SEQUENCE.splitlines())
    + "  ```\n"
)
ER_SCHEMA = """\
type: object
title: ER 図
properties:
  id: {type: string, title: ID}
  title: {type: string, title: タイトル}
  er:
    title: ER 図
    x-heading: ER 図
    x-shape: diagram
    x-diagram: er
    properties:
      entities:
        type: array
        items:
          properties: {name: {title: 名前}}
      relations:
        type: array
        items:
          properties:
            from: {title: 元}
            from_column: {title: 元の列}
            from_cardinality: {title: 元の多重度}
            to: {title: 先}
            to_column: {title: 先の列}
            to_cardinality: {title: 先の多重度}
  tables:
    type: array
    title: テーブル
    x-heading: テーブル
    x-shape: sections
    x-key: name
"""
ER_DOC = """\
id: doc-8
title: 'ER 図: 販売'
er:
  entities:
    - name: 顧客
    - name: 注文
      columns:
        - {type: bigint, name: id, key: PK}
        - {type: bigint, name: customer_id, key: FK, comment: '参照: 顧客.id'}
    - name: 商品
    - name: 支払い
  relations:
    - from: 顧客
      from_column: id
      from_cardinality: '1'
      to: 注文
      to_column: customer_id
      to_cardinality: 0..n
      label: 注文する
    - from: 顧客
      from_column: id
      from_cardinality: '1'
      to: 支払い
      to_column: customer_id
      to_cardinality: 0..n
    - from: 注文
      from_column: product_id
      from_cardinality: 0..n
      to: 商品
      to_column: id
      to_cardinality: '1'
tables:
  - name: customers
    title: 顧客
    columns:
      - {name: id, title: 顧客 ID, type: bigint, primary_key: true, not_null: true}
      - {name: email, title: メール, type: text}
  - name: payments
    title: 支払い
    columns:
      - {name: id, title: 支払い ID, type: bigint, primary_key: true}
      - {name: customer_id, title: 顧客 ID, type: bigint, foreign_key: {table: customers.id}}
"""
DECIDED_SCHEMA = """\
type: object
title: 検討事項を持つ文書
properties:
  id: {type: string, title: ID}
  title: {type: string, title: タイトル}
  items:
    title: 一覧
    x-heading: 一覧
    x-shape: table
    items:
      properties: {name: {title: 名前}, decisions: {title: 検討事項}}
  spec:
    type: object
    title: 仕様
    x-heading: 仕様
    properties:
      kind: {title: 種類}
      limit: {title: 上限}
      owner: {title: 担当}
      decisions: {type: array, title: 検討事項}
  decisions: {type: array, title: 検討事項}
"""
DECIDED_DOC = """\
id: doc-8
title: 検討事項の文書 8
items:
  - {name: 項目 1, decisions: [D-1, D-2, D-3]}
spec: {kind: 定期, limit: 3, owner: 運用, decisions: [D-1, D-2, D-3]}
decisions: [D-1, D-2, D-3]
"""
LINKED_DOC = (
    "id: doc-1\n"
    "name: 文書 1\n"
    "description: >-\n"
    "  [文書 2](id:doc-2) と [項目](id:doc-6#flow) と [無い項目](id:doc-6#no-such-item)\n"
    "  と [無い文書](id:no-such-doc) と `[コード](id:doc-2)`\n"
)
CROSSING_DOC = """\
id: doc-9
title: 図の文書 9
flow:
  nodes:
    - {id: a, label: 受付, kind: action}
    - {id: b, label: 確認, kind: action}
    - {id: c, label: あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほ, kind: result}
  edges:
    - {from: a, to: b}
    - {from: b, to: c}
    - {from: a, to: c, label: 直接}
    - {from: c, to: a, label: 再送}
  frame: {label: 処理, nodes: [a, c]}
states:
  initial: 下書き
  final: [マージ済み]
  states: [{name: 下書き}, {name: レビュー待ち}, {name: 修正中}, {name: マージ済み}]
  transitions:
    - {from: 下書き, to: レビュー待ち, trigger: レビューを依頼する}
    - {from: レビュー待ち, to: 修正中, trigger: 指摘を受ける}
    - {from: 修正中, to: レビュー待ち, trigger: 依頼し直す}
    - {from: 修正中, to: 修正中, trigger: commit を積む}
    - {from: 下書き, to: マージ済み, trigger: そのままマージする}
chart: |-
  ```mermaid
  flowchart LR
    a[受付] --> b[確認]
    b --> c[保存]
    a --> c
    c --> a
  ```
"""
# 文書の取得の結合テストで図を検査する、`package.json` の `devDependencies` でバージョンを固定した mdmark の CLI
MDMARK_CLI = REPO_ROOT / "node_modules" / ".bin" / "mdmark"
# mdmark の定義の検査が出すフロー図のずれの種類
FLOW_CHECK_KINDS = {
    "diagram_invalid",
    "diagram_node_overlap",
    "diagram_node_overflow",
    "diagram_wire_crosses_node",
    "diagram_label_too_long",
}
# `mdmark check --text -` の標準出力の、ずれ 1 つの行（`-:{行}: {種類}: {内容}`）の種類
CHECK_LINE_KIND = re.compile(r"^-:\d+: (\S+?):", re.M)
FLOW_BLOCK = re.compile(r"<!-- flow -->\n\n```json\n(.*?)\n```\n\n<!-- /flow -->", re.S)
ER_BLOCK = re.compile(r"<!-- er -->\n\n```json\n(.*?)\n```\n\n<!-- /er -->", re.S)


def _sample(*extra: dict[str, Any], doc_1: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """文書 1・文書 2 と、`extra` の文書の並びを作る。"""
    return [
        doc_1 or doc("doc-1", "docs/doc-1.yaml", data=TABLE_DATA, updated=UPDATED),
        doc("doc-2", "docs/doc-2.yaml", data={"id": "doc-2", "name": "文書 2"}),
        *extra,
    ]


def _page_changes(items: list[dict[str, Any]]) -> dict[str, str | None]:
    """サイドバーの項目の入れ子をたどり、page の文書のパスと変化を対応させる。"""
    changes: dict[str, str | None] = {}
    for item in items:
        if item["kind"] == "page":
            changes[item["path"]] = item["change"]
        changes.update(_page_changes(item["items"]))
    return changes


def _outline(items: list[dict[str, Any]]) -> list[Any]:
    """サイドバーの項目を、page は文書のパス、group は（名前, 中の並び）にした入れ子にする。"""
    return [
        item["path"] if item["kind"] == "page" else (item["title"], _outline(item["items"]))
        for item in items
    ]


def test_normal(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """一番左のタブの一番上の文書と、文書のパスで指した文書を返却する（正常系）。"""
    # 準備
    real_index.serve("sample", IndexSource(docs={None: _sample()}, nav=NAV))
    env = make_server(real_index)
    # 実行
    top = env.client.get("/_api/sources/sample/docs")
    second = env.client.get("/_api/sources/sample/docs/docs/doc-2")
    # 検証
    body = top.json()
    assert top.status_code == 200
    assert body["path"] == "docs/doc-1"
    assert [tab["title"] for tab in body["tabs"]] == ["規約", "補足"]
    assert [tab["active"] for tab in body["tabs"]] == [True, False]
    assert "## 項目" in body["markdown"]
    assert "| キー | 名称 | 備考 |" in body["markdown"]
    assert len(body["tableKeys"]) == 1
    assert body["conversionError"] is None
    assert body["diff"] is None
    assert set(_page_changes(body["tabs"][0]["items"]).values()) == {None}
    assert datetime.fromisoformat(body["updatedAt"]) == datetime.fromisoformat(UPDATED)
    assert second.status_code == 200
    assert "# 文書 2" in second.json()["markdown"]


def test_normal_when_nav_missing(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """nav が無い配信元は種類ごとにタブを作り、文書をフォルダでまとめる（正常系）。"""
    # 準備
    documents = [
        doc("doc-1", "docs/doc-1.yaml"),
        doc("lang-index", "docs/lang/index.yaml"),
        doc("ts", "docs/lang/ts.yaml"),
        doc("py-style", "docs/lang/py/style.yaml"),
        doc("n-1", "notes/n-1.yaml", kind="memo"),
    ]
    rows = [row("sample", ["docs/**/*.yaml"]), row("memo", ["notes/*.yaml"], title="メモ")]
    real_index.serve("plain", IndexSource(documents=rows, docs={None: documents}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/plain/docs")
    # 検証
    tabs = response.json()["tabs"]
    assert response.status_code == 200
    assert [tab["title"] for tab in tabs] == ["sample", "メモ"]
    assert _outline(tabs[0]["items"]) == [
        "docs/doc-1",
        ("lang", ["docs/lang/index", "docs/lang/ts", ("py", ["docs/lang/py/style"])]),
    ]
    assert _outline(tabs[1]["items"]) == ["notes/n-1"]


def test_normal_when_ref_given(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """ref のリビジョンの文書を返却する（正常系）。"""
    # 準備
    renamed = doc("doc-1", "docs/doc-1.yaml", data={"id": "doc-1", "name": "新しい名前"})
    real_index.serve("sample", IndexSource(docs={None: _sample(doc_1=renamed), "old": _sample()}))
    env = make_server(real_index)
    # 実行
    at_old = env.client.get("/_api/sources/sample/docs/docs/doc-1", params={"ref": "old"})
    at_default = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    # 検証
    assert at_old.status_code == 200
    assert "# 文書 1" in at_old.json()["markdown"]
    assert at_old.json()["ref"] == "old"
    assert "# 新しい名前" in at_default.json()["markdown"]
    assert at_default.json()["ref"] == "develop"


def test_normal_when_diff_given(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """diff のリビジョンから変わった項目と、サイドバーの page ごとの変化を返却する（正常系）。"""
    # 準備
    parent = _sample(doc("doc-3", "docs/doc-3.yaml"))
    renamed = doc(
        "doc-1", "docs/doc-1.yaml", data={**TABLE_DATA, "name": "新しい名前"}, version="v-new"
    )
    changed = _sample(doc("doc-4", "docs/doc-4.yaml"), doc_1=renamed)
    real_index.serve(
        "sample", IndexSource(docs={None: changed, "changed": changed, "parent": parent})
    )
    env = make_server(real_index)
    # 実行
    response = env.client.get(
        "/_api/sources/sample/docs/docs/doc-1", params={"ref": "changed", "diff": "parent"}
    )
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["diff"] == {"base": "parent", "change": "modified", "changedItems": ["name"]}
    assert "# 新しい名前" in body["markdown"]
    assert _page_changes(body["tabs"][0]["items"]) == {
        "docs/doc-1": "modified",
        "docs/doc-2": None,
        "docs/doc-3": "deleted",
        "docs/doc-4": "added",
    }


def _custom_source(**overrides: Any) -> IndexSource:
    """`converters[]` を指す行 custom と、埋め込みのマーカーを持つ本文の行 guide を持つ配信元を作る。"""
    rows = [
        row("sample", ["docs/*.yaml"]),
        row("custom", ["custom/*.yaml"], converter="md"),
        row("guide", ["guide/files.yaml"], records="files"),
    ]
    documents = _sample(
        doc("c-1", "custom/c-1.yaml", kind="custom", data={"id": "c-1", "name": "カスタム 1"}),
        doc(
            "guide/intro.md",
            "guide/files.yaml",
            kind="guide",
            record_index=0,
            body_path="guide/intro.md",
            body="# 案内\n\n<!-- embed: data/rows.yaml#rows -->\n",
            data={"path": "intro.md"},
        ),
    )
    values: dict[str, Any] = {"documents": rows, "docs": {None: documents}, **overrides}
    return IndexSource(**values)


def test_normal_when_custom_converter(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index の変換の結果と、埋め込みのマーカーの表を返却する（正常系）。"""
    # 準備
    rows_doc = doc(
        "rows", "data/rows.yaml", kind="data", data={"rows": [{"colA": "値A", "colB": "値B"}]}
    )
    details = {
        "custom/c-1.yaml": {"markdown": "# カスタム変換: カスタム 1\n"},
        "data/rows.yaml": {"document": rows_doc},
    }
    source = _custom_source(details=details)
    # 埋め込みの元の文書は、本物の project-index が配信する行に配置する
    source.documents.append(row("data", ["data/*.yaml"], {"type": "object"}))
    real_index.serve("custom", source)
    env = make_server(real_index)
    # 実行
    converted = env.client.get("/_api/sources/custom/docs/custom/c-1")
    embedded = env.client.get("/_api/sources/custom/docs/guide/files/guide/intro.md")
    # 検証
    assert converted.status_code == 200
    assert "# カスタム変換: カスタム 1" in converted.json()["markdown"]
    assert embedded.status_code == 200
    assert "| colA | colB |" in embedded.json()["markdown"]
    assert "embed:" not in embedded.json()["markdown"]


def test_normal_when_conversion_failed(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index が返却した変換の失敗と読み込めなかった YAML を conversionError に入れる（正常系）。"""
    # 準備（custom の converters[] のスクリプトは終了コード 1 で終わる）
    failure = {"reason": "exit", "kind": "custom", "detail": "終了コード 1"}
    source = _custom_source(details={"custom/c-1.yaml": {"failure": failure}})
    source.docs[None] = [item for item in source.docs[None] if item["id"] != "doc-1"]
    source.unreadable = [
        {
            "reason": "invalid_yaml",
            "kind": "sample",
            "detail": "閉じていない",
            "file": "docs/doc-1.yaml",
            "line": 1,
            "column": 1,
        }
    ]
    real_index.serve("custom", source)
    env = make_server(real_index)
    # 実行
    failed = env.client.get("/_api/sources/custom/docs/custom/c-1")
    schema_driven = env.client.get("/_api/sources/custom/docs/docs/doc-2")
    unreadable = env.client.get("/_api/sources/custom/docs/docs/doc-1")
    # 検証
    error = failed.json()["conversionError"]
    assert failed.status_code == 200
    assert failed.json()["markdown"] is None
    assert (error["reason"], error["kind"]) == ("exit", "custom")
    assert "scripts/convert_fail.py" in error["script"]
    assert "変換に失敗しました" in error["detail"]
    assert schema_driven.status_code == 200
    assert "# 文書 2" in schema_driven.json()["markdown"]
    broken = unreadable.json()["conversionError"]
    assert unreadable.status_code == 200
    assert unreadable.json()["markdown"] is None
    assert (broken["reason"], broken["file"], broken["line"], broken["column"]) == (
        "invalid_yaml",
        "docs/doc-1.yaml",
        1,
        1,
    )


def test_error_when_not_found(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """無い配信元・リビジョン・文書を断り、何が無いかを返却する（異常系）。"""
    # 準備
    real_index.serve("sample", IndexSource(docs={None: _sample()}))
    real_index.serve(
        "broken",
        IndexSource(errors=[{"path": "documents[0].paths", "reason": "必須のキーが無い"}]),
    )
    env = make_server(real_index)
    # 実行
    no_doc = env.client.get("/_api/sources/sample/docs/no-such-doc")
    no_ref = env.client.get("/_api/sources/sample/docs", params={"ref": "no-such-branch"})
    not_served = env.client.get("/_api/sources/broken/docs")
    unknown = env.client.get("/_api/sources/unknown/docs")
    # 検証
    assert no_doc.status_code == 404
    assert (no_doc.json()["missing"], no_doc.json()["value"]) == ("doc", "no-such-doc")
    assert no_ref.status_code == 404
    assert (no_ref.json()["missing"], no_ref.json()["value"]) == ("ref", "no-such-branch")
    assert not_served.status_code == 404
    assert not_served.json()["missing"] == "not_served"
    assert [error["path"] for error in not_served.json()["errors"]] == ["documents[0].paths"]
    assert unknown.status_code == 404
    assert (unknown.json()["missing"], unknown.json()["value"]) == ("source", "unknown")


def test_normal_when_nav_filtered_by_tags(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """auto の filter に該当する文書だけをタブのサイドバーに並べる（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {
                "title": "mcp",
                "items": [
                    {
                        "auto": {
                            "document": "sample",
                            "filter": {
                                "and": [
                                    {"field": "tags", "op": "eq", "values": ["mcp"]},
                                    {"not": {"field": "tags", "op": "eq", "values": ["設計"]}},
                                ]
                            },
                        }
                    }
                ],
            },
            {"title": "すべて", "items": [{"auto": {"document": "sample"}}]},
        ]
    }
    documents = [
        doc(
            f"doc-{n}",
            f"docs/doc-{n}.yaml",
            data={"id": f"doc-{n}", "name": f"文書 {n}", "tags": tags},
        )
        for n, tags in [(1, ["mcp"]), (2, ["mcp", "設計"]), (3, ["設計"])]
    ]
    real_index.serve("sample", IndexSource(docs={None: documents}, nav=nav))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    # 検証
    tabs = {tab["title"]: tab for tab in response.json()["tabs"]}
    assert response.status_code == 200
    assert list(_page_changes(tabs["mcp"]["items"])) == ["docs/doc-1"]
    assert list(_page_changes(tabs["すべて"]["items"])) == [
        "docs/doc-1",
        "docs/doc-2",
        "docs/doc-3",
    ]


def _alias(doc_id: str, path: str, kind: str, **values: Any) -> dict[str, Any]:
    """`alias_type` を持つ行の文書を作る。"""
    data = {"id": doc_id, **values}
    return doc(doc_id, path, kind=kind, data=data, metadata=data)


def test_normal_when_aliases_returned(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """alias_type を持つ行の文書のエイリアスを文書といっしょに返却する（正常系）。"""
    # 準備
    rows = [
        row("sample", ["docs/*.yaml"]),
        row("terms", ["terms/*.yaml"], aliasType="term"),
        row("refs", ["refs/*.yaml"], aliasType="doc"),
    ]
    documents = _sample(
        _alias(
            "scope",
            "terms/scope.yaml",
            "terms",
            alias_type="term",
            name="作業範囲",
            aliases=["scope", "担当範囲"],
            avoid=["担当領域"],
            description="触ってよい範囲",
        ),
        _alias(
            "settings",
            "refs/settings.yaml",
            "refs",
            alias_type="doc",
            name="設定のリファレンス",
            aliases=["settings"],
            description="設定のキーの一覧",
        ),
    )
    real_index.serve("sample", IndexSource(documents=rows, docs={None: documents}))
    real_index.serve("plain", IndexSource(docs={None: _sample()}))
    env = make_server(real_index)
    # 実行
    with_aliases = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    without = env.client.get("/_api/sources/plain/docs")
    # 検証
    aliases = {item["name"]: item for item in with_aliases.json()["aliases"]}
    term = aliases["作業範囲"]
    ref = aliases["設定のリファレンス"]
    assert with_aliases.status_code == 200
    assert (term["aliasType"], term["aliases"], term["avoid"]) == (
        "term",
        ["scope", "担当範囲"],
        ["担当領域"],
    )
    assert term["description"] == "触ってよい範囲"
    assert (ref["aliasType"], ref["aliases"]) == ("doc", ["settings"])
    assert ref.get("avoid") is None
    assert without.status_code == 200
    assert without.json()["aliases"] == []


def test_normal_when_body_path_given(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """管理用の YAML の行の文書に bodyPath を返却し、本文のファイルのパスで指した文書を返却する（正常系）。"""
    # 準備
    rows = [row("sample", ["docs/*.yaml"]), row("notes", ["notes/files.yaml"], records="files")]
    notes = [
        doc(
            f"notes/{name}.md",
            "notes/files.yaml",
            kind="notes",
            record_index=index,
            body_path=f"notes/{name}.md",
            body=f"# {name.upper()} の本文\n",
            data={"path": f"{name}.md"},
        )
        for index, name in enumerate(["a", "b"])
    ]
    real_index.serve("sample", IndexSource(documents=rows, docs={None: _sample(*notes)}))
    env = make_server(real_index)
    # 実行
    by_page = env.client.get("/_api/sources/sample/docs/notes/files/notes/a.md")
    by_body_path = env.client.get("/_api/sources/sample/docs/notes/b.md")
    plain = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    # 検証
    assert by_page.status_code == 200
    assert (by_page.json()["bodyPath"], by_page.json()["path"]) == (
        "notes/a.md",
        "notes/files/notes/a.md",
    )
    assert by_body_path.status_code == 200
    assert by_body_path.json()["path"] == "notes/files/notes/b.md"
    assert "# B の本文" in by_body_path.json()["markdown"]
    assert by_body_path.json()["bodyPath"] == "notes/b.md"
    assert plain.status_code == 200
    assert plain.json()["bodyPath"] is None


def test_normal_when_nav_grouped_by_folder(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """group_by: '@folder' の auto が、手で記載した page の文書を除いてフォルダごとの group を作る（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {
                "title": "ルール",
                "items": [
                    {"page": "rules/common"},
                    {"auto": {"document": "rules", "group_by": "@folder"}},
                ],
            }
        ]
    }
    rules = [
        doc(doc_id, path, kind="rules")
        for doc_id, path in [
            ("common", "rules/common.yaml"),
            ("lang-index", "rules/lang/index.yaml"),
            ("ts", "rules/lang/ts.yaml"),
            ("py-style", "rules/lang/py/style.yaml"),
        ]
    ]
    rows = [row("sample", ["docs/*.yaml"]), row("rules", ["rules/**/*.yaml"])]
    real_index.serve("sample", IndexSource(documents=rows, docs={None: _sample(*rules)}, nav=nav))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    # 検証
    tabs = {tab["title"]: tab for tab in response.json()["tabs"]}
    assert response.status_code == 200
    assert _outline(tabs["ルール"]["items"]) == [
        "rules/common",
        ("lang", ["rules/lang/index", "rules/lang/ts", ("py", ["rules/lang/py/style"])]),
    ]


def _drawn_source() -> IndexSource:
    """図の文書の種類と文書 6・7 を持つ配信元を作る。"""
    rows = [
        row("sample", ["docs/*.yaml"]),
        row("drawn", ["drawn/*.yaml"], load_yaml(DRAWN_SCHEMA)),
    ]
    drawn = [
        doc(doc_id, f"drawn/{doc_id}.yaml", kind="drawn", data=load_yaml(text))
        for doc_id, text in [("doc-6", DRAWN_DOC), ("doc-7", UNREADABLE_DOC)]
    ]
    return IndexSource(documents=rows, docs={None: _sample(*drawn)})


def test_normal_when_schema_document_drawn(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """図を mdmark の部品に、スカラーの並びを「項目 / 値」の表にした Markdown を返却する（正常系）。"""
    # 準備
    real_index.serve("sample", _drawn_source())
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/drawn/doc-6")
    # 検証
    markdown = response.json()["markdown"]
    assert response.status_code == 200
    assert markdown.count("<!-- flow -->") == 3
    assert markdown.count("<!-- sequence -->") == 1
    assert "```mermaid" not in markdown
    flows = [json.loads(block) for block in FLOW_BLOCK.findall(markdown)]
    flowchart, states = flows[0], flows[1]
    nodes = {node["id"]: node for node in flowchart["nodes"]}
    assert (nodes["q"]["kind"], nodes["q"]["hint"], nodes["r"]["kind"]) == (
        "question",
        "保存の判定",
        "result",
    )
    wire = flowchart["wires"][0]
    assert (wire["label"], wire["line"], wire["tip"]) == ("YES", "read", "保存の判定の詳細")
    assert flowchart["frame"]["title"] == "判定"
    kinds = {node["name"]: node["kind"] for node in states["nodes"]}
    assert (kinds["開始"], kinds["下書き"], kinds["公開"], kinds["終了"]) == (
        "start",
        "action",
        "action",
        "result",
    )
    assert "| 種類 | 定期 |" in markdown
    assert "**全件実行**\n\n```bash\nuv run pytest\n```" in markdown
    assert markdown.startswith("# 図の文書 6\n\n図と表で読む文書\n")
    assert "内部メモの値" not in markdown


def test_normal_when_mermaid_unreadable(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """読み取れない行を含む Mermaid を、図ごと Mermaid のコードブロックのまま返却する（正常系）。"""
    # 準備
    real_index.serve("sample", _drawn_source())
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/drawn/doc-7")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert "<!-- sequence -->" not in body["markdown"]
    assert f"```mermaid\n{UNREADABLE_SEQUENCE}\n```" in body["markdown"]
    assert body["conversionError"] is None


def _er_columns(definition: dict[str, Any], table_id: str) -> list[tuple[str, bool, bool, bool]]:
    """ER 図の定義の `table_id` のテーブルの列の名前と `pk`・`fk`・`nn` の組。"""
    table = next(t for t in definition["tables"] if t["id"] == table_id)
    return [
        (c["name"], bool(c.get("pk")), bool(c.get("fk")), bool(c.get("nn")))
        for c in table["columns"]
    ]


def test_normal_when_er_diagram_drawn(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """`x-diagram: er` の項目を、テーブルの列で補った mdmark の ER 図の部品にする（正常系）。"""
    # 準備
    rows = [row("sample", ["docs/*.yaml"]), row("er", ["er/*.yaml"], load_yaml(ER_SCHEMA))]
    er = doc("doc-8", "er/販売.yaml", kind="er", data=load_yaml(ER_DOC))
    real_index.serve("sample", IndexSource(documents=rows, docs={None: _sample(er)}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/er/販売")
    # 検証
    markdown = response.json()["markdown"]
    match = ER_BLOCK.search(markdown)
    assert response.status_code == 200
    assert match is not None
    assert markdown.count("<!-- er -->") == 1
    assert "erDiagram" not in markdown
    definition = json.loads(match.group(1))
    assert [t["id"] for t in definition["tables"]] == ["顧客", "注文", "商品", "支払い"]
    assert _er_columns(definition, "顧客") == [
        ("id", True, False, True),
        ("email", False, False, False),
    ]
    assert _er_columns(definition, "注文") == [
        ("id", True, False, False),
        ("customer_id", False, True, False),
    ]
    assert _er_columns(definition, "商品") == []
    assert _er_columns(definition, "支払い") == [
        ("id", True, False, False),
        ("customer_id", False, True, False),
    ]


def test_normal_when_flow_layout_checked(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """線がノードを横切りやすい構造のフロー図を、mdmark の定義の検査で配置のずれが出ない部品にする（正常系）。"""
    # 準備
    assert MDMARK_CLI.exists(), "mdmark の CLI が無い。リポジトリの直下で `npm ci` を実行する"
    rows = [row("sample", ["docs/*.yaml"]), row("drawn", ["drawn/*.yaml"], load_yaml(DRAWN_SCHEMA))]
    crossing = doc("doc-9", "drawn/doc-9.yaml", kind="drawn", data=load_yaml(CROSSING_DOC))
    real_index.serve("sample", IndexSource(documents=rows, docs={None: _sample(crossing)}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/drawn/doc-9")
    markdown = response.json()["markdown"]
    checked = subprocess.run(
        [str(MDMARK_CLI), "check", "--text", "-"],
        input=markdown,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    # 検証
    assert response.status_code == 200
    assert markdown.count("<!-- flow -->") == 3
    # 点検を終えた: 最後に `ずれ {件数} 件` の行がある
    assert "ずれ" in checked.stdout, checked.stderr
    assert not set(CHECK_LINE_KIND.findall(checked.stdout)) & FLOW_CHECK_KINDS, checked.stdout


def test_normal_when_id_link_resolved(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """本文の `id:` のリンクを、同じ配信元の文書と、その項目の見出しのアンカーへのリンクにする（正常系）。"""
    # 準備
    source = _drawn_source()
    linked = doc("doc-1", "docs/doc-1.yaml", data=load_yaml(LINKED_DOC))
    source.docs[None] = [linked, *source.docs[None][1:]]
    real_index.serve("sample", source)
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert "[文書 2](doc-2.yaml)" in body["markdown"]
    assert "[項目](../drawn/doc-6.yaml#処理の流れ)" in body["markdown"]
    assert "[無い項目](../drawn/doc-6.yaml)" in body["markdown"]
    assert "[無い文書](id:no-such-doc)" in body["markdown"]
    assert "`[コード](id:doc-2)`" in body["markdown"]
    assert body["conversionError"] is None


def _decided_source() -> IndexSource:
    """`decisions.folders` に 2 つの話し合いの記録のフォルダを持つ配信元を作る。"""
    rows = [
        row("sample", ["docs/*.yaml"]),
        row("decided", ["decided/*.yaml"], load_yaml(DECIDED_SCHEMA)),
    ]
    decided = doc("doc-8", "decided/doc-8.yaml", kind="decided", data=load_yaml(DECIDED_DOC))
    return IndexSource(
        documents=rows,
        docs={None: _sample(decided)},
        nav=NAV,
        decision_folders=["tmp/a", "tmp/b"],
        decisions={"D-1": 1, "D-2": 2},
        decision_texts={"D-1": "# D-1 の本文\n"},
    )


def test_normal_when_decision_linked(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """`decisions` の ID のうち 1 つのフォルダに決まる ID を、検討事項の文書へのリンクにする（正常系）。"""
    # 準備
    real_index.serve("sample", _decided_source())
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/decided/doc-8")
    # 検証
    body = response.json()
    markdown = body["markdown"]
    assert response.status_code == 200
    assert "| 項目 1 | [D-1](../_decisions/D-1)・D-2・D-3 |" in markdown
    assert markdown.count("- [D-1](../_decisions/D-1)") == 2
    assert markdown.count("- D-2") == 2
    assert markdown.count("- D-3") == 2
    assert "[D-2]" not in markdown
    assert body["conversionError"] is None


def test_normal_when_decision_document_returned(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """`path` が `_decisions/{ID}` のとき、project-index が返却した検討事項の文書を返却する（正常系）。"""
    # 準備
    real_index.serve("sample", _decided_source())
    env = make_server(real_index)
    before = datetime.now(tz=UTC)
    # 実行
    found = env.client.get("/_api/sources/sample/docs/_decisions/D-1")
    ambiguous = env.client.get("/_api/sources/sample/docs/_decisions/D-2")
    missing = env.client.get("/_api/sources/sample/docs/_decisions/D-3")
    # 検証
    body = found.json()
    assert found.status_code == 200
    assert (body["path"], body["markdown"]) == ("_decisions/D-1", "# D-1 の本文\n")
    assert [tab["active"] for tab in body["tabs"]] == [False, False]
    assert datetime.fromisoformat(body["updatedAt"]) >= before
    assert (body["bodyPath"], body["diff"]) == (None, None)
    assert ambiguous.status_code == 404
    assert (ambiguous.json()["missing"], ambiguous.json()["value"]) == ("doc", "_decisions/D-2")
    assert missing.status_code == 404
    assert (missing.json()["missing"], missing.json()["value"]) == ("doc", "_decisions/D-3")


def test_error_when_project_index_unreachable(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index につながらなければ 503 を返却し、つながった後は同じ要求が 200 になる（異常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource(docs={None: _sample()}))
    env = make_server(mock_index)
    port = mock_index.port
    mock_index.stop()
    # 実行
    refused = env.client.get("/_api/sources/sample/docs")
    mock_index.start(port)
    recovered = env.client.get("/_api/sources/sample/docs")
    # 検証
    assert refused.status_code == 503
    assert refused.headers["content-type"].startswith("application/problem+json")
    assert refused.json()["projectIndex"]["address"] == mock_index.address
    assert refused.json()["projectIndex"]["reason"]
    assert recovered.status_code == 200


def test_error_when_project_index_timed_out(
    mock_index: MockIndex,
    make_server: Callable[..., ServerEnv],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """project-index が制限時間を過ぎても応答しなければ打ち切って 503 を返却する（異常系）。"""
    # 準備
    monkeypatch.setattr("dev_docs.main.PROJECT_INDEX_TIMEOUT_SEC", 1)
    mock_index.serve("sample", IndexSource(docs={None: _sample()}))
    env = make_server(mock_index)
    mock_index.delay_sec = 3
    started = time.monotonic()
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    # 検証
    elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert response.json()["projectIndex"]["address"] == mock_index.address
    assert "1 秒以内に応答がありませんでした" in response.json()["projectIndex"]["reason"]
    assert elapsed < 2.5
