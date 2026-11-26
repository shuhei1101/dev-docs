from __future__ import annotations

import asyncio
import json
import re
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from dev_docs.features.view.document_lists import DOCUMENT_LIST_CACHE_SIZE
from dev_docs.shared.yaml_io import load_yaml

from .conftest import (
    GUIDE_BODY,
    REPO_ROOT,
    IndexSource,
    MockIndex,
    RealIndex,
    ServerEnv,
    body_source,
    doc,
    note_value,
    row,
)

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
UNMAPPABLE_CLASS = "classDiagram\n  class 文書\n  文書 : +id"
UNMAPPABLE_DOC = (
    "id: doc-7\ntitle: 図の文書 7\nsequence: |-\n  ```mermaid\n"
    + "".join(f"  {line}\n" for line in UNMAPPABLE_CLASS.splitlines())
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
CLICKED_DOC = DRAWN_DOC.replace(
    "  frame: {label: 判定, nodes: [q, r]}\n",
    "  frame: {label: 判定, nodes: [q, r]}\n"
    "  clicks:\n"
    "    - {id: q, href: 'id:doc-2'}\n"
    "    - {id: r, href: 'id:no-such-doc'}\n"
    "    - {id: z, href: 'id:doc-2'}\n",
)
CLICKED_CHART = (
    "flowchart TD\n"
    "  A[受付] --> B[保存]\n"
    "  B --> C[通知]\n"
    '  click A "id:doc-6#flow"\n'
    '  click B href "id:doc-2"\n'
    '  click C "id:no-such-doc"'
)
CLICKED_LINKED_DOC = (
    "id: doc-1\nname: 文書 1\ndescription: |-\n  ```mermaid\n"
    + "".join(f"  {line}\n" for line in CLICKED_CHART.splitlines())
    + "  ```\n"
)
CLASS_CHART = (
    "classDiagram\n"
    "  class A\n"
    "  class B\n"
    '  click A href "id:doc-6#flow"\n'
    '  click B "id:doc-6#flow"\n'
    '  click C href "id:no-such-doc#"\n'
    '  click D href "https://example.com/"'
)
CLASS_LINKED_DOC = (
    "id: doc-1\nname: 文書 1\ndescription: |-\n  ```mermaid\n"
    + "".join(f"  {line}\n" for line in CLASS_CHART.splitlines())
    + "  ```\n"
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
# 文書の取得の結合テストで図を点検する mdmark の CLI の参照（既定は develop の最新。固定するときはタグか commit の SHA に書き換える）
MDMARK_REF = "develop"
# 画面が `mount` に指定する map の設定（`map.kinds`・`map.lines`）
MDMARK_MAP = (
    REPO_ROOT / "frontend" / "src" / "features" / "docs" / "doc-view" / "hooks" / "mdmark-map.json"
)
# `mdmark check --text -` の標準出力の、ずれ 1 つの行（`-:{行}: {種類}: {内容}`）の種類
CHECK_LINE_KIND = re.compile(r"^-:\d+: (\S+?):", re.M)
# 表のマーカー（`<!-- table: {JSON} -->`）の JSON の引数
TABLE_MARKER = re.compile(r"^<!-- table: (\{.*\}) -->$", re.M)
# 表のマーカーと、直後の表の見出しの行
MARKED_TABLE = re.compile(r"^<!-- table: (\{.*\}) -->\n(\|.*\|)$", re.M)
# map の範囲の Mermaid のコードブロックと、続く補足
MAP_BLOCK = re.compile(
    r"<!-- map: \{.*?\} -->\n\n```mermaid\n(.*?)\n```(?:\n\n<!-- map-data: (\{.*?\}) -->)?\n\n<!-- /map -->",
    re.S,
)


def _maps(markdown: str) -> list[tuple[list[str], dict[str, Any]]]:
    """map の範囲ごとの Mermaid の行（前後の空白を除く）と補足（無ければ空）。"""
    return [
        (
            [line.strip() for line in code.splitlines() if line.strip()],
            json.loads(data) if data else {},
        )
        for code, data in MAP_BLOCK.findall(markdown)
    ]


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


def test_normal_when_nav_grouped_by_common_keys(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """group_by に共通のキーと行の metadata で対応付けたキーを指定した auto が、値ごとの group を作る（正常系）。"""
    # 準備
    schema = {
        "type": "object",
        "title": "サンプル",
        "properties": {
            "id": {"type": "string", "title": "ID"},
            "name": {"type": "string", "title": "名前"},
            "main_tags": {"type": "array", "title": "主題", "items": {"type": "string"}},
            "分類": {"type": "string", "title": "分類"},
        },
    }
    nav = {
        "tabs": [
            {"title": "主題", "items": [{"auto": {"document": "sample", "group_by": "main_tags"}}]},
            {"title": "分類", "items": [{"auto": {"document": "sample", "group_by": "category"}}]},
        ]
    }
    rows = [row("sample", ["docs/*.yaml"], schema, metadata={"category": "分類"})]
    documents = [
        doc(
            "doc-1",
            "docs/doc-1.yaml",
            data={"id": "doc-1", "name": "文書 1", "main_tags": ["topic:a"], "分類": "x"},
        ),
        doc(
            "doc-2",
            "docs/doc-2.yaml",
            data={"id": "doc-2", "name": "文書 2", "main_tags": ["topic:b"], "分類": "x"},
        ),
        doc("doc-3", "docs/doc-3.yaml", data={"id": "doc-3", "name": "文書 3"}),
    ]
    real_index.serve("sample", IndexSource(documents=rows, docs={None: documents}, nav=nav))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    # 検証
    tabs = {tab["title"]: tab for tab in response.json()["tabs"]}
    assert response.status_code == 200
    assert _outline(tabs["主題"]["items"]) == [
        ("topic:a", ["docs/doc-1"]),
        ("topic:b", ["docs/doc-2"]),
        ("その他", ["docs/doc-3"]),
    ]
    assert _outline(tabs["分類"]["items"]) == [
        ("x", ["docs/doc-1", "docs/doc-2"]),
        ("その他", ["docs/doc-3"]),
    ]


def _drawn_source() -> IndexSource:
    """図の文書の種類と文書 6・7 を持つ配信元を作る。"""
    rows = [
        row("sample", ["docs/*.yaml"]),
        row("drawn", ["drawn/*.yaml"], load_yaml(DRAWN_SCHEMA)),
    ]
    drawn = [
        doc(doc_id, f"drawn/{doc_id}.yaml", kind="drawn", data=load_yaml(text))
        for doc_id, text in [("doc-6", DRAWN_DOC), ("doc-7", UNMAPPABLE_DOC)]
    ]
    return IndexSource(documents=rows, docs={None: _sample(*drawn)})


def test_normal_when_schema_document_drawn(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """図を mdmark の map の範囲の Mermaid に、スカラーの並びを「項目 / 値」の表にした Markdown を返却する（正常系）。"""
    # 準備
    real_index.serve("sample", _drawn_source())
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/drawn/doc-6")
    # 検証
    markdown = response.json()["markdown"]
    maps = _maps(markdown)
    assert response.status_code == 200
    assert markdown.count("<!-- map: ") == 4
    assert len(maps) == 4
    assert "<!-- flow -->" not in markdown
    assert "<!-- sequence -->" not in markdown
    (flow, data), (states, _) = maps[0], maps[1]
    assert flow[0] == "flowchart TD"
    assert 'q["保存するか"]:::question' in flow
    assert 'r["保存する"]:::result' in flow
    start = flow.index('subgraph frame ["判定"]')
    assert flow[start + 1 : flow.index("end", start)] == [
        'q["保存するか"]:::question',
        'r["保存する"]:::result',
    ]
    assert data["notes"]["q"]["text"] == "保存の判定"
    assert data["notes"]["q->r"]["text"] == "保存の判定の詳細"
    assert data["layout"]["q->r"]["line"] == "read"
    assert states[0] == "stateDiagram-v2"
    names = {
        line.split(" as ")[1]: line.split('"')[1] for line in states if line.startswith("state ")
    }
    ids = {name: state_id for state_id, name in names.items()}
    assert f"[*] --> {ids['下書き']}" in states
    assert f"{ids['下書き']} --> {ids['公開']} : 公開する" in states
    assert f"{ids['公開']} --> [*]" in states
    assert "| 種類 | 定期 |" in markdown
    assert "**全件実行**\n\n```bash\nuv run pytest\n```" in markdown
    assert markdown.startswith("# 図の文書 6\n\n図と表で読む文書\n")
    assert "内部メモの値" not in markdown
    # 表のマーカーは JSON の記載: 図の元データの表は閉じ、ノードの表は ID の列を隠す
    markers = _table_markers(markdown)
    closed = [marker for marker in markers if marker.get("collapse") == {"open": False}]
    hidden = [
        name
        for marker in closed
        for name, setting in marker.get("columns", {}).items()
        if setting.get("hidden") is True
    ]
    assert closed
    assert hidden == ["ID"] * len(hidden)
    assert hidden
    assert all(" table: data" not in line for line in markdown.splitlines())
    tables = _marked_tables(markdown)
    # 辺の表（`元`・`先` の列を持つ表）のマーカーは `hidden` の列を持たない
    edges = [marker for marker, head in tables if {"元", "先"} <= set(head)]
    assert edges
    assert all(
        "hidden" not in setting
        for marker in edges
        for setting in marker.get("columns", {}).values()
    )
    # 説明の列を持つ表のマーカーは、説明の列を折り返さない
    described = [marker for marker, head in tables if "説明" in head]
    assert described
    assert all(marker["columns"]["説明"] == {"width": {"mode": "nowrap"}} for marker in described)


def test_normal_when_mermaid_not_mappable(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """map で描けない種類の Mermaid を、Mermaid のコードブロックのまま返却する（正常系）。"""
    # 準備
    real_index.serve("sample", _drawn_source())
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/drawn/doc-7")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert "<!-- map" not in body["markdown"]
    assert f"```mermaid\n{UNMAPPABLE_CLASS}\n```" in body["markdown"]
    assert body["conversionError"] is None


def _table_markers(markdown: str) -> list[dict[str, Any]]:
    """本文の表のマーカーの JSON の引数を、出る順に返却する。"""
    return [json.loads(args) for args in TABLE_MARKER.findall(markdown)]


def _marked_tables(markdown: str) -> list[tuple[dict[str, Any], list[str]]]:
    """本文の表のマーカーの JSON の引数と、直後の表の列名を、出る順に返却する。"""
    return [
        (json.loads(args), [cell.strip() for cell in head.strip("|").split("|")])
        for args, head in MARKED_TABLE.findall(markdown)
    ]


def _er_entity(lines: list[str], name: str) -> list[str]:
    """`erDiagram` の `name` の実体の列の行。"""
    start = lines.index(f"{name} {{")
    return lines[start + 1 : lines.index("}", start)]


def test_normal_when_er_diagram_drawn(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """`x-diagram: er` の項目を、テーブルの列で補った `erDiagram` の map の範囲にする（正常系）。"""
    # 準備
    rows = [row("sample", ["docs/*.yaml"]), row("er", ["er/*.yaml"], load_yaml(ER_SCHEMA))]
    er = doc("doc-8", "er/販売.yaml", kind="er", data=load_yaml(ER_DOC))
    real_index.serve("sample", IndexSource(documents=rows, docs={None: _sample(er)}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/er/販売")
    # 検証
    markdown = response.json()["markdown"]
    maps = _maps(markdown)
    assert response.status_code == 200
    assert len(maps) == 1
    assert "<!-- er -->" not in markdown
    lines = maps[0][0]
    assert lines[0] == "erDiagram"
    assert _er_entity(lines, "顧客") == ["bigint id PK", "text email"]
    assert _er_entity(lines, "注文") == ["bigint id PK", 'bigint customer_id FK "参照: 顧客.id"']
    assert _er_entity(lines, "商品") == []
    assert _er_entity(lines, "支払い") == ["bigint id PK", 'bigint customer_id FK "参照: 顧客.id"']
    relations = [line for line in lines if "--" in line]
    assert relations == ['顧客 ||--o{ 注文 : "注文する"', '顧客 ||--o{ 支払い : ""']
    assert "product_id" in markdown.split("<!-- /map -->")[1]
    # 図の元データの表は、`collapse.open` が `false` の JSON の表のマーカーで閉じる
    assert any(marker.get("collapse") == {"open": False} for marker in _table_markers(markdown))


def test_normal_when_diagrams_checked(
    real_index: RealIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """線がノードを横切りやすい構造の図を、mdmark の点検で書き方の警告が出ない map の範囲にする（正常系）。"""
    # 準備
    config = tmp_path / "mdmark.config.yaml"
    # JSON は YAML として読める
    config.write_text(
        json.dumps({"map": json.loads(MDMARK_MAP.read_text(encoding="utf-8"))}, ensure_ascii=False),
        encoding="utf-8",
    )
    rows = [row("sample", ["docs/*.yaml"]), row("drawn", ["drawn/*.yaml"], load_yaml(DRAWN_SCHEMA))]
    crossing = doc("doc-9", "drawn/doc-9.yaml", kind="drawn", data=load_yaml(CROSSING_DOC))
    real_index.serve("sample", IndexSource(documents=rows, docs={None: _sample(crossing)}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/drawn/doc-9")
    markdown = response.json()["markdown"]
    checked = subprocess.run(
        [
            "npx",
            "-y",
            f"github:shuhei1101/mdmark#{MDMARK_REF}",
            "check",
            "--text",
            "-",
            "--config",
            str(config),
        ],
        input=markdown,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    # 検証
    assert response.status_code == 200
    assert markdown.count("<!-- map: ") == 3
    # 点検を終えた: 最後に `ずれ {件数} 件` の行がある
    assert "ずれ" in checked.stdout, checked.stderr
    # ずれが 0 件（表のマーカーの前の記載方法の `legacy_mark` も無い）
    assert CHECK_LINE_KIND.findall(checked.stdout) == [], checked.stdout


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


def test_normal_when_diagram_node_id_link_resolved(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """フロー図の `clicks` と手で記載したフローチャートの `click` の `id:` を、ノードのリンクにする（正常系）。"""
    # 準備
    source = _drawn_source()
    clicked = doc("doc-6", "drawn/doc-6.yaml", kind="drawn", data=load_yaml(CLICKED_DOC))
    linked = doc("doc-1", "docs/doc-1.yaml", data=load_yaml(CLICKED_LINKED_DOC))
    source.docs[None] = [
        linked,
        *(clicked if item["id"] == "doc-6" else item for item in source.docs[None][1:]),
    ]
    real_index.serve("sample", source)
    env = make_server(real_index)
    # 実行
    drawn = env.client.get("/_api/sources/sample/docs/drawn/doc-6")
    charted = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    # 検証
    assert drawn.status_code == 200
    assert charted.status_code == 200
    flow = next(lines for lines, _ in _maps(drawn.json()["markdown"]) if lines[0] == "flowchart TD")
    assert 'click q "../docs/doc-2.yaml"' in flow
    assert not any(line.startswith(("click r", "click z", "z[")) for line in flow)
    chart = _maps(charted.json()["markdown"])[0][0]
    assert 'click A "../drawn/doc-6.yaml#処理の流れ"' in chart
    assert 'click B href "doc-2.yaml"' in chart
    assert not any(line.startswith("click C") for line in chart)
    assert [line for line in chart if not line.startswith("click")] == [
        line.strip() for line in CLICKED_CHART.splitlines() if not line.strip().startswith("click")
    ]
    for response in (drawn, charted):
        assert not re.search(r'click \S+ (?:href )?"id:', response.json()["markdown"])
        assert response.json()["conversionError"] is None


def test_normal_when_mermaid_click_id_resolved(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """Mermaid のまま返す図の `click` の `id:` を、文書の相対パスと見出しのアンカーにする（正常系）。"""
    # 準備
    source = _drawn_source()
    linked = doc("doc-1", "docs/doc-1.yaml", data=load_yaml(CLASS_LINKED_DOC))
    source.docs[None] = [linked, *source.docs[None][1:]]
    real_index.serve("sample", source)
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    # 検証
    body = response.json()
    assert response.status_code == 200
    block = re.search(r"```mermaid\n(.*?)\n```", body["markdown"], re.S)
    assert block is not None, body["markdown"]
    lines = [line.strip() for line in block.group(1).splitlines()]
    assert lines[0] == "classDiagram"
    assert 'click A href "../drawn/doc-6.yaml#処理の流れ"' in lines
    assert 'click B "../drawn/doc-6.yaml#処理の流れ"' in lines
    assert not any(line.startswith("click C") for line in lines)
    assert 'click D href "https://example.com/"' in lines
    assert "<!-- map" not in body["markdown"]
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
    """project-index が文書の取得の制限時間を過ぎても応答しなければ打ち切って 503 を返却する（異常系）。"""
    # 準備（問い合わせごとの制限時間は、文書の取得の制限時間より長くする）
    monkeypatch.setattr("dev_docs.main.PROJECT_INDEX_TIMEOUT_SEC", 10)
    monkeypatch.setattr("dev_docs.features.view.document.DOCUMENT_FETCH_TIMEOUT_SEC", 1)
    mock_index.serve("sample", IndexSource(docs={None: _sample()}))
    env = make_server(mock_index)
    mock_index.delay_sec = 3
    started = time.monotonic()
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    # 検証
    elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()["projectIndex"]
    assert problem["kind"] == "timeout"
    assert problem["address"] == mock_index.address
    assert "1 秒以内に応答がありませんでした" in problem["reason"]
    assert elapsed < 2.5


def _wait_for_requests(mock: MockIndex, count: int) -> None:
    """偽物が `count` 件の要求を受け付けるまで待つ（5 秒で打ち切る）。"""
    deadline = time.monotonic() + 5
    while len(mock.received) < count and time.monotonic() < deadline:
        time.sleep(0.05)


def _times(mock: MockIndex, event: str, path: str) -> list[float]:
    """偽物が `path` の要求を受け付けた・応答した時刻を並べる。"""
    return [at for kind, found, at in mock.timeline if kind == event and found == path]


def test_normal_when_requests_sent_concurrently(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """配信元の設定とリビジョンの一覧を同時に問い合わせ、文書の一覧をリビジョンの一覧の応答の後に問い合わせる（正常系）。"""
    # 準備（問い合わせごとに 1 秒、配信元の設定だけ 2 秒待つ偽物）
    mock_index.serve("sample", IndexSource(docs={None: _sample()}))
    env = make_server(mock_index)
    mock_index.timeline.clear()
    mock_index.delay_sec = 1
    mock_index.path_delays["/sources/sample/config"] = 2
    started = time.monotonic()
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    elapsed = time.monotonic() - started
    # 検証
    config_received = _times(mock_index, "received", "/sources/sample/config")[0]
    refs_received = _times(mock_index, "received", "/sources/sample/refs")[0]
    docs_received = _times(mock_index, "received", "/sources/sample/docs")[0]
    first_answered = min(at for kind, _, at in mock_index.timeline if kind == "answered")
    config_answered = _times(mock_index, "answered", "/sources/sample/config")[0]
    assert response.status_code == 200
    assert response.json()["path"] == "docs/doc-1"
    assert 3 <= elapsed < 4
    assert max(config_received, refs_received) < first_answered
    assert docs_received < config_answered


C0 = "0000000"
C1 = "1111111"
C2 = "2222222"


def _main_refs(commit: str) -> dict[str, Any]:
    """main が `commit` を指すリビジョンの一覧の応答（IF-29）を作る。"""
    return {
        "git": True,
        "defaultRef": "main",
        "branches": [{"name": "main", "commit": commit}],
        "tags": [],
        "commits": [],
    }


def _named(name: str) -> list[dict[str, Any]]:
    """文書 1 の `name` を `name` にした sample の文書の並び。"""
    return _sample(
        doc_1=doc("doc-1", "docs/doc-1.yaml", data={"id": "doc-1", "name": name}, version=name)
    )


def _cached_source() -> IndexSource:
    """main が変更の commit（C1）を指し、親の commit（C0）を持つ配信元 sample。"""
    current = _named("文書 1 の変更後")
    return IndexSource(
        docs={None: current, "main": current, C1: current, C0: _named("文書 1")},
        refs=_main_refs(C1),
    )


def _list_refs(mock: MockIndex, source_id: str = "sample") -> list[str | None]:
    """偽物が受け付けた文書の一覧の要求の `ref` を、受け付けた順に並べる。"""
    found: list[str | None] = []
    for _, raw, _ in mock.received:
        url = urlsplit(raw)
        if url.path == f"/sources/{source_id}/docs":
            found.append(parse_qs(url.query).get("ref", [None])[0])
    return found


def _view(response: Any) -> dict[str, Any]:
    """応答のうち保持の有無で変わってはいけない項目を取り出す。"""
    body = response.json()
    return {key: body[key] for key in ("path", "markdown", "tabs", "diff", "ref")}


def test_normal_when_document_list_reused(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """同じ配信元の同じ commit の文書の一覧を保持し、2 回目以降の取得では問い合わせない（正常系）。"""
    # 準備
    mock_index.serve("sample", _cached_source())
    env = make_server(mock_index)
    fresh = make_server(mock_index)
    paths = [
        "/_api/sources/sample/docs/docs/doc-1",
        "/_api/sources/sample/docs/docs/doc-2",
        f"/_api/sources/sample/docs/docs/doc-1?diff={C0}",
        f"/_api/sources/sample/docs/docs/doc-2?diff={C0}",
    ]
    mock_index.received.clear()
    # 実行
    responses = [env.client.get(path) for path in paths]
    listed = _list_refs(mock_index)
    expected = [_view(fresh.client.get(path)) for path in paths[1:]]
    # 検証
    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    assert sorted(str(ref) for ref in listed) == [C0, C1]
    assert [_view(response) for response in responses[1:]] == expected
    assert responses[0].json()["ref"] == "main"


def _send_together(env: ServerEnv, paths: list[str]) -> list[Any]:
    """`paths` の取得を別々のスレッドで同時に送信し、応答を並べる。"""
    responses: dict[int, Any] = {}
    threads = [
        threading.Thread(target=lambda n=n, p=p: responses.update({n: env.client.get(p)}))
        for n, p in enumerate(paths)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return [responses[n] for n in range(len(paths))]


def test_normal_when_document_list_shared(
    mock_index: MockIndex,
    make_server: Callable[..., ServerEnv],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同じ組の文書の一覧を取得している間に届いた取得は、その問い合わせの結果を共有する（正常系）。"""
    # 準備（文書の一覧の問い合わせだけ 1 秒待つ偽物）
    monkeypatch.setattr("dev_docs.main.PROJECT_INDEX_TIMEOUT_SEC", 10)
    mock_index.serve("sample", _cached_source())
    mock_index.path_delays["/sources/sample/docs"] = 1
    paths = [
        f"/_api/sources/sample/docs/docs/doc-1?ref=main&diff={C0}",
        f"/_api/sources/sample/docs/docs/doc-1?ref={C0}",
    ]
    shared_env = make_server(mock_index)
    mock_index.received.clear()
    # 実行（同時に送信する）
    shared = _send_together(shared_env, paths)
    shared_refs = _list_refs(mock_index)
    # 実行（文書の一覧の問い合わせに 500 を返却させて同時に送信し、戻してもう一度送信する）
    failing_env = make_server(mock_index)
    mock_index.failing.add("/sources/sample/docs")
    mock_index.received.clear()
    failed = _send_together(failing_env, paths)
    mock_index.failing.clear()
    retried = failing_env.client.get(paths[1])
    retried_refs = _list_refs(mock_index)
    # 実行（先に届いた取得をクライアントの側で取り消す）
    cancel_env = make_server(mock_index)
    mock_index.received.clear()
    held = threading.Event()
    mock_index.path_holds["/sources/sample/docs"] = held
    cancelled, survivor = asyncio.run(_cancel_first(cancel_env, paths[1], mock_index))
    held.set()
    cancel_refs = _list_refs(mock_index)
    # 検証
    assert [response.status_code for response in shared] == [200, 200]
    assert shared_refs.count(C0) == 1
    assert [response.status_code for response in failed] == [502, 502]
    assert retried.status_code == 200
    assert retried_refs.count(C0) == 2
    assert cancelled
    assert survivor.status_code == 200
    assert survivor.json()["markdown"] == shared[1].json()["markdown"]
    assert cancel_refs.count(C0) == 1


def _wait_for_list(mock: MockIndex) -> None:
    """偽物が文書の一覧の要求を受け付けるまで待つ（5 秒で打ち切る）。"""
    deadline = time.monotonic() + 5
    while not _list_refs(mock) and time.monotonic() < deadline:
        time.sleep(0.05)


async def _cancel_first(env: ServerEnv, path: str, mock: MockIndex) -> tuple[bool, Any]:
    """同じ取得を 2 つ送信し、先に送信した取得を文書の一覧の問い合わせが届いた後に取り消す。"""
    transport = httpx.ASGITransport(app=env.client.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = asyncio.create_task(client.get(path))
        # 先の取得の文書の一覧の問い合わせが偽物に届くまで待つ
        await asyncio.to_thread(_wait_for_list, mock)
        second = asyncio.create_task(client.get(path))
        await asyncio.sleep(0.2)
        first.cancel()
        try:
            await first
        except asyncio.CancelledError:
            cancelled = True
        else:
            cancelled = False
        hold = mock.path_holds.pop("/sources/sample/docs")
        hold.set()
        return cancelled, await second


def test_normal_when_revision_or_config_changed(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """ブランチが別の commit を指したときと、配信元の設定の応答が変わったときは文書の一覧を取り直す（正常系）。"""
    # 準備
    source = mock_index.serve("sample", _cached_source())
    env = make_server(mock_index)
    path = "/_api/sources/sample/docs/docs/doc-1"
    advanced = _named("文書 1 を進めた後")
    mock_index.received.clear()
    # 実行
    before = env.client.get(path)
    source.refs = _main_refs(C2)
    source.docs[C2] = advanced
    source.docs[None] = advanced
    moved = env.client.get(path)
    moved_refs = _list_refs(mock_index)
    source.nav = {"tabs": [{"title": "新しいタブ", "items": [{"auto": {"document": "sample"}}]}]}
    reconfigured = env.client.get(path)
    reconfigured_refs = _list_refs(mock_index)
    pinned = env.client.get(f"{path}?ref={C2}")
    pinned_refs = _list_refs(mock_index)
    # 検証
    assert before.status_code == 200
    assert moved_refs == [C1, C2]
    assert "文書 1 を進めた後" in moved.json()["markdown"]
    assert reconfigured.status_code == 200
    assert reconfigured_refs == [C1, C2, C2]
    assert [tab["title"] for tab in reconfigured.json()["tabs"]] == ["新しいタブ"]
    assert pinned.status_code == 200
    assert pinned_refs == reconfigured_refs


def test_normal_when_cache_limit_exceeded(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """保持する組が上限を超えたら、最も前に使用した組を捨てる（正常系）。"""
    # 準備（保持する文書の一覧の数より 1 つ多い commit）
    commits = [f"{n}{n}{n}{n}{n}{n}a" for n in range(DOCUMENT_LIST_CACHE_SIZE + 1)]
    source = IndexSource(docs={None: _sample()}, refs=_main_refs(commits[-1]))
    for commit in commits:
        source.docs[commit] = _sample()
    mock_index.serve("sample", source)
    env = make_server(mock_index)
    path = "/_api/sources/sample/docs/docs/doc-1"
    for commit in commits:
        env.client.get(f"{path}?ref={commit}")
    mock_index.received.clear()
    # 実行
    first = env.client.get(f"{path}?ref={commits[0]}")
    first_refs = _list_refs(mock_index)
    last = env.client.get(f"{path}?ref={commits[-1]}")
    last_refs = _list_refs(mock_index)
    # 検証
    assert first.status_code == 200
    assert first_refs == [commits[0]]
    assert last.status_code == 200
    assert last_refs == [commits[0]]


def test_normal_when_document_list_not_cacheable(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """Git 管理外の配信元は文書の一覧を保持せず、取得のたびに問い合わせる（正常系）。"""
    # 準備
    mock_index.serve("notes", IndexSource(docs={None: _sample()}, git=False))
    env = make_server(mock_index)
    mock_index.received.clear()
    # 実行
    responses = [env.client.get("/_api/sources/notes/docs") for _ in range(2)]
    # 検証
    assert [response.status_code for response in responses] == [200, 200]
    assert _list_refs(mock_index, "notes") == [None, None]


def test_normal_when_gzip_accepted(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """`Accept-Encoding` に gzip を含む要求に、応答を gzip で返却する（正常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource(docs={None: _sample()}))
    env = make_server(mock_index)
    path = "/_api/sources/sample/docs/docs/doc-1"
    # 実行
    gzipped = env.client.get(path, headers={"Accept-Encoding": "gzip"})
    identity = env.client.get(path, headers={"Accept-Encoding": "identity"})
    # 検証
    assert gzipped.status_code == 200
    assert gzipped.headers["content-encoding"] == "gzip"
    assert "content-encoding" not in identity.headers
    assert gzipped.json() == identity.json()


def test_error_when_project_index_failed(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index が 5xx を返却したら 502 と project-index の detail を返却する（異常系）。"""
    # 準備
    detail = "git archive --format=tar abc123: 20 秒を超えたため止めました"
    mock_index.serve("sample", IndexSource(docs={None: _sample()}))
    env = make_server(mock_index)
    mock_index.queued[("GET", "/sources/sample/config")] = [(500, {"detail": detail})]
    # 実行
    failed = env.client.get("/_api/sources/sample/docs")
    recovered = env.client.get("/_api/sources/sample/docs")
    # 検証
    assert failed.status_code == 502
    assert failed.headers["content-type"].startswith("application/problem+json")
    problem = failed.json()["projectIndex"]
    assert problem["kind"] == "failed"
    assert problem["address"] == mock_index.address
    assert problem["reason"] == detail
    assert recovered.status_code == 200


def test_normal_when_search_excluded(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """検索から除外される文書もサイドバーに並べ、page に `excluded: true` を付ける（正常系）。"""
    # 準備
    documents = [doc("doc-1", "docs/doc-1.yaml"), doc("doc-2", "docs/doc-2.yaml")]
    excluded = {"field": "id", "op": "eq", "values": ["doc-2"]}
    rows = [row("sample", ["docs/*.yaml"], search_exclude=excluded)]
    real_index.serve("sample", IndexSource(documents=rows, docs={None: documents}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/docs")
    # 検証
    pages = {
        item["path"]: item["excluded"]
        for item in response.json()["tabs"][0]["items"]
        if item["kind"] == "page"
    }
    assert response.status_code == 200
    assert pages == {"docs/doc-1": False, "docs/doc-2": True}


def test_normal_when_edit_returned(
    body_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """直コミットできる YAML と Markdown の文書に、本文の編集の情報を返却する（正常系）。"""
    # 準備
    body_source(body_index)
    env = make_server(body_index)
    refs = env.client.get("/_api/sources/sample/refs").json()
    head = next(item["commit"] for item in refs["branches"] if item["name"] == refs["defaultRef"])
    listed = httpx.get(f"{body_index.address}/sources/sample/docs", timeout=60).json()
    version = next(item["version"] for item in listed["documents"] if item["id"] == "n1")
    # 実行
    note = env.client.get("/_api/sources/sample/docs/notes/n1")
    guide = env.client.get("/_api/sources/sample/docs/files/guide.md")
    # 検証
    assert note.status_code == 200, note.json()
    body = note.json()
    edit = body["edit"]
    assert edit["language"] == "yaml"
    assert load_yaml(edit["source"]) == note_value("n1")
    assert head.startswith(edit["baseCommit"]) or edit["baseCommit"].startswith(head)
    assert (edit["version"], edit["kind"]) == (version, "note")
    assert [(block["path"], block["type"]) for block in edit["blocks"]] == [
        ("status", "enum"),
        ("summary", "string"),
        ("#items[i1].body", "markdown"),
        ("rows", "table"),
    ]
    blocks = {block["path"]: block for block in edit["blocks"]}
    assert blocks["status"]["options"] == ["draft", "current"]
    assert blocks["rows"]["columns"] == ["word", "replacement"]
    assert blocks["rows"]["value"] == note_value("n1")["rows"]
    assert all(block["markdown"] in body["markdown"] for block in edit["blocks"])
    assert edit["titleBlock"]["path"] == "title"
    assert "title" not in blocks
    assert guide.status_code == 200, guide.json()
    guide_edit = guide.json()["edit"]
    assert guide_edit["language"] == "markdown"
    assert guide_edit["source"] == GUIDE_BODY
    assert (guide_edit["blocks"], guide_edit["titleBlock"]) == ([], None)


def _sqlite_log(path: Path) -> None:
    """SQLite の表 logs（行 1 件）のファイルを作る。"""
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("create table logs (id text, message text)")
        connection.execute("insert into logs values ('l1', 'ログ')")
        connection.commit()


def test_normal_when_not_editable(
    body_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """書き込みの API が断る文書と既定のブランチでないリビジョンには edit を返却しない（正常系）。"""
    # 準備
    text = {"type": "string"}
    documents = [
        {"id": "memo", "paths": ["memos/*.yaml"], "schema": "schemas/memo.schema.yaml"},
        {
            "id": "log",
            "sqlite": {
                "file": "logs.db",
                "table": "logs",
                "columns": [
                    {"name": "id", "description": "ID"},
                    {"name": "message", "description": "内容"},
                ],
            },
        },
    ]
    files = {
        "schemas/memo.schema.yaml": json.dumps(
            {"type": "object", "properties": {"id": text, "name": text}}
        ),
        "memos/m1.yaml": json.dumps({"id": "m1", "name": "メモ"}, ensure_ascii=False),
    }
    source = body_source(
        body_index,
        kinds=["note", "terms", {"id": "guide", "body": False}, "log"],
        write_api_kinds=["note", "terms", "guide", "log"],
        extra_documents=documents,
        extra_files=files,
    )
    old = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source.develop, check=True, capture_output=True, text=True
    ).stdout.strip()
    (source.develop / "notes" / "n1.yaml").write_text(
        json.dumps(note_value("n1", summary="修正後の概要"), ensure_ascii=False), encoding="utf-8"
    )
    for args in (["commit", "-qam", "概要"], ["push", "-q"]):
        subprocess.run(["git", *args], cwd=source.develop, check=True, capture_output=True)
    # SQLite の表は配信元のフォルダのファイルを読み込む
    _sqlite_log(source.repo / "logs.db")
    env = make_server(body_index)
    log_path = next(
        item["path"]
        for tab in env.client.get("/_api/sources/sample/docs/notes/n1").json()["tabs"]
        for item in tab["items"]
        if tab["title"] == "log"
    )
    # 実行
    responses = {
        name: env.client.get(f"/_api/sources/sample/docs/{path}")
        for name, path in {
            "guide": "files/guide.md",
            "memo": "memos/m1",
            "log": log_path,
            "old": f"notes/n1?ref={old}",
            "latest": "notes/n1",
        }.items()
    }
    # 検証
    for name in ("guide", "memo", "log", "old"):
        assert responses[name].status_code == 200, (name, responses[name].json())
        assert responses[name].json()["edit"] is None, name
        assert responses[name].json()["markdown"], name
    assert responses["latest"].json()["edit"] is not None
