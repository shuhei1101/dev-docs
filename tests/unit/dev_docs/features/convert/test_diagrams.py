from __future__ import annotations

import json
import re
from typing import Any

import pytest

from dev_docs.features.convert.diagrams import render_diagram, render_mermaid
from dev_docs.features.convert.types import DiagramHead

HEAD = DiagramHead(title="図", scope="文書", updated="2026-11-03")


def _definition(block: str, marker: str) -> dict[str, Any]:
    """部品の範囲から定義の JSON を取り出す。"""
    match = re.search(
        rf"<!-- {marker} -->\n\n```json\n(.*?)\n```\n\n<!-- /{marker} -->", block, re.S
    )
    assert match is not None, block
    definition: dict[str, Any] = json.loads(match.group(1))
    return definition


def test_render_diagram() -> None:
    """フローチャート（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "x"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    definition = _definition(result, "flow")
    assert (definition["title"], definition["scope"], definition["updated"]) == (
        "図",
        "文書",
        "2026-11-03",
    )
    assert [node["name"] for node in definition["nodes"]] == ["A", "B"]
    assert [wire["label"] for wire in definition["wires"]] == ["x"]
    assert "```mermaid" not in result


def test_render_diagram_when_node_kinds() -> None:
    """箱の種類（正常系）。"""
    # 準備
    value = {
        "nodes": [
            {"id": "a", "kind": "actor"},
            {"id": "b", "kind": "store"},
            {"id": "c", "kind": "process"},
        ],
        "edges": [],
    }
    # 実行
    result = render_diagram(value, "dataflow", HEAD)
    # 検証
    assert [node["kind"] for node in _definition(result, "flow")["nodes"]] == [
        "external",
        "data",
        "script",
    ]


def test_render_diagram_when_state() -> None:
    """状態遷移（正常系）。"""
    # 準備
    value = {
        "initial": "下書き",
        "final": ["公開"],
        "states": [{"name": "下書き"}, {"name": "公開"}],
        "transitions": [
            {"from": "下書き", "to": "公開", "trigger": "公開する", "condition": "承認済み"},
            {"from": "公開", "to": "下書き", "trigger": "取り下げる"},
        ],
    }
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    definition = _definition(result, "flow")
    subs = {node["name"]: node.get("sub") for node in definition["nodes"]}
    assert subs == {"下書き": "初期状態", "公開": "終了状態"}
    assert definition["wires"][0]["label"] == "公開する [承認済み]"


CUSTOMERS = {
    "name": "customers",
    "title": "顧客",
    "summary": "注文する人",
    "columns": [
        {"name": "id", "title": "顧客 ID", "type": "bigint", "primary_key": True, "not_null": True},
        {"name": "email", "title": "メール", "type": "text"},
    ],
}
# 支払いと顧客の関連（`||--o{`）
PAYMENT_RELATION = {
    "entities": [{"name": "顧客"}, {"name": "支払い"}],
    "relations": [{"from": "顧客", "to": "支払い", "cardinality": "||--o{"}],
}


def _payments(reference: str) -> dict[str, Any]:
    """`customer_id` の外部キーが `reference` を指す支払いのテーブル。"""
    return {
        "name": "payments",
        "title": "支払い",
        "columns": [
            {"name": "id", "title": "支払い ID", "type": "bigint", "primary_key": True},
            {
                "name": "customer_id",
                "title": "顧客 ID",
                "type": "bigint",
                "foreign_key": {"table": reference},
            },
        ],
    }


def _table(definition: dict[str, Any], table_id: str) -> dict[str, Any]:
    """ER 図の定義から `id` のテーブルを取り出す。"""
    table: dict[str, Any] = next(t for t in definition["tables"] if t["id"] == table_id)
    return table


def _columns(table: dict[str, Any]) -> list[tuple[str, bool, bool, bool]]:
    """テーブルの列の名前と `pk`・`fk`・`nn` の組。"""
    return [
        (column["name"], bool(column.get("pk")), bool(column.get("fk")), bool(column.get("nn")))
        for column in table["columns"]
    ]


def _ends(definition: dict[str, Any]) -> list[tuple[str, str]]:
    """ER 図の定義の関連の `fromColumn`・`toColumn` の組。"""
    return [(r["fromColumn"], r["toColumn"]) for r in definition["relations"]]


def test_render_diagram_when_er() -> None:
    """ER 図（正常系）。"""
    # 準備
    value = {
        "entities": [
            {"name": "顧客"},
            {
                "name": "注文",
                "columns": [
                    {"type": "bigint", "name": "id", "key": "PK"},
                    {
                        "type": "bigint",
                        "name": "customer_id",
                        "key": "FK",
                        "comment": "参照: 顧客.id",
                    },
                ],
            },
        ],
        "relations": [{"from": "顧客", "to": "注文", "cardinality": "||--o{", "label": "注文する"}],
    }
    # 実行
    result = render_diagram(value, "er", HEAD, tables=[CUSTOMERS])
    # 検証
    definition = _definition(result, "er")
    assert _table(definition, "顧客")["name"] == "customers"
    assert _columns(_table(definition, "顧客")) == [
        ("id", True, False, True),
        ("email", False, False, False),
    ]
    assert _columns(_table(definition, "注文")) == [
        ("id", True, False, False),
        ("customer_id", False, True, False),
    ]
    assert definition["relations"] == [
        {
            "from": "顧客",
            "fromColumn": "id",
            "fromCard": "1",
            "to": "注文",
            "toColumn": "customer_id",
            "toCard": "0..n",
            "label": "注文する",
        }
    ]
    assert "```mermaid" not in result


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("customers.id", id="physical"),
        pytest.param("顧客.id", id="logical"),
    ],
)
def test_render_diagram_when_er_table_foreign_key(reference: str) -> None:
    """テーブルの列の外部キー（正常系）。"""
    # 準備
    tables = [CUSTOMERS, _payments(reference)]
    # 実行
    result = render_diagram(PAYMENT_RELATION, "er", HEAD, tables=tables)
    # 検証
    assert _ends(_definition(result, "er")) == [("id", "customer_id")]


@pytest.mark.parametrize(
    ("classification", "expected"),
    [
        pytest.param("注文", [("id", "customer_id")], id="own"),
        pytest.param("請求", [], id="other"),
    ],
)
def test_render_diagram_when_er_own_classification(
    classification: str, expected: list[tuple[str, str]]
) -> None:
    """自分の分類を付けたテーブルの列の外部キー（正常系）。"""
    # 準備
    tables = [CUSTOMERS, _payments("注文/customers.id")]
    # 実行
    result = render_diagram(
        PAYMENT_RELATION, "er", HEAD, tables=tables, classification=classification
    )
    # 検証
    assert _ends(_definition(result, "er")) == expected


def test_render_diagram_when_er_reverse_foreign_key() -> None:
    """元の実体が外部キーを持つ（正常系）。"""
    # 準備
    value = {
        "entities": [
            {
                "name": "注文",
                "columns": [
                    {
                        "type": "bigint",
                        "name": "customer_id",
                        "key": "FK",
                        "comment": "参照: 顧客.id",
                    }
                ],
            },
            {"name": "顧客", "columns": [{"type": "bigint", "name": "id", "key": "PK"}]},
        ],
        "relations": [{"from": "注文", "to": "顧客", "cardinality": "}o--||"}],
    }
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    relation = _definition(result, "er")["relations"][0]
    assert relation["fromColumn"] == "customer_id"
    assert relation["toColumn"] == "id"
    assert relation["fromCard"] == "0..n"
    assert relation["toCard"] == "1"


def test_render_diagram_when_er_unresolved() -> None:
    """端の列が決まらない関連と読み替えられない多重度（正常系）。"""
    # 準備
    value = {
        "entities": [
            {
                "name": "注文",
                "columns": [
                    {"type": "bigint", "name": "id", "key": "PK"},
                    {
                        "type": "bigint",
                        "name": "customer_id",
                        "key": "FK",
                        "comment": "参照: 顧客.id",
                    },
                ],
            },
            {"name": "顧客", "columns": [{"type": "bigint", "name": "id", "key": "PK"}]},
            {"name": "商品"},
        ],
        "relations": [
            {"from": "注文", "to": "商品", "cardinality": "}o--||"},
            {"from": "顧客", "to": "注文", "cardinality": "||..xx"},
        ],
    }
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    definition = _definition(result, "er")
    assert definition["relations"] == []
    assert _table(definition, "商品")["columns"] == []


def test_render_diagram_when_er_layout() -> None:
    """格子の配置（正常系）。"""
    # 準備
    columns = [{"type": "int", "name": "a"}, {"type": "int", "name": "b"}]
    value = {
        "entities": [
            {"name": "t0", "columns": columns},
            {"name": "t1", "columns": columns},
            {"name": "t2", "columns": columns},
            {"name": "t3", "columns": columns},
        ]
    }
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    definition = _definition(result, "er")
    assert [(t["x"], t["y"], t["w"]) for t in definition["tables"]] == [
        (24, 24, 240),
        (360, 24, 240),
        (696, 24, 240),
        (24, 172, 240),
    ]
    assert definition["width"] == 960


def test_render_diagram_when_unknown() -> None:
    """知らない種類（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match="gantt"):
        render_diagram({}, "gantt", HEAD)  # type: ignore[arg-type]


def test_render_mermaid() -> None:
    """シーケンス図（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  participant A as 画面\n  A->>B: 読む"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    definition = _definition(result, "sequence")
    assert [p["name"] for p in definition["participants"]] == ["画面", "B"]
    assert [step["label"] for step in definition["steps"]] == ["読む"]


def test_render_mermaid_when_flowchart() -> None:
    """フローチャート（正常系）。"""
    # 実行
    result = render_mermaid("flowchart TD\n  a --> b", HEAD)
    # 検証
    assert len(_definition(result, "flow")["nodes"]) == 2


def test_render_mermaid_when_unreadable() -> None:
    """読み取れないコード（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  A->>B: 読む\n  Note over A: 補足"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    assert result == f"```mermaid\n{code}\n```"
