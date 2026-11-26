from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

from .conftest import IndexSource, RealIndex, ServerEnv, body_source, doc, note_value, row

URL = "/_api/sources/{source}/preview"
CUSTOM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "title": "ID"},
        "name": {"type": "string", "title": "名前"},
        "steps": {
            "type": "array",
            "title": "手順",
            "x-heading": "手順",
            "items": {"type": "object", "properties": {"text": {"type": "string"}}},
        },
    },
}


def _status(source_repo: object) -> str:
    """配信元のフォルダの git status。"""
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(source_repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_normal(body_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """書き換えた YAML を、文書の取得と同じ変換で Markdown にして返却する（正常系）。"""
    # 準備
    source = body_source(body_index)
    env = make_server(body_index)
    edit = env.client.get("/_api/sources/sample/docs/notes/n1").json()["edit"]
    content = edit["source"].replace("summary: 概要", "summary: 修正後の概要")
    before = (_status(source.repo), _status(source.develop))
    # 実行
    response = env.client.post(
        URL.format(source="sample"), json={"path": "notes/n1", "content": content}
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert "修正後の概要" in data["markdown"]
    assert (data["conversionError"], data["fallback"]) == (None, False)
    assert (_status(source.repo), _status(source.develop)) == before
    # 同じ値の文書を既定のブランチへ入れ、文書の取得の Markdown と比べる
    (source.develop / "notes" / "n1.yaml").write_text(
        json.dumps(note_value("n1", summary="修正後の概要"), ensure_ascii=False), encoding="utf-8"
    )
    for args in (["commit", "-qam", "概要"], ["push", "-q"]):
        subprocess.run(["git", *args], cwd=source.develop, check=True, capture_output=True)
    fetched = env.client.get("/_api/sources/sample/docs/notes/n1").json()
    assert data["markdown"] == fetched["markdown"]


def test_normal_when_yaml_invalid(
    body_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """読み込めない content は、行と列を conversionError に入れて返却する（正常系）。"""
    # 準備
    body_source(body_index)
    env = make_server(body_index)
    content = "id: n1\ntitle: メモ\n\tsummary: 概要\n"
    # 実行
    response = env.client.post(
        URL.format(source="sample"), json={"path": "notes/n1", "content": content}
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["markdown"] is None
    error = data["conversionError"]
    assert error["line"] == 3
    assert error["column"] is not None
    assert error["reason"]


def test_normal_when_custom_converter(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """converters[] を指す種類は、スキーマ駆動の変換で描いて fallback を返却する（正常系）。"""
    # 準備
    rows = [row("custom", ["custom/*.yaml"], CUSTOM_SCHEMA, converter="md")]
    value = {"id": "c-1", "name": "カスタム 1", "steps": [{"text": "1 つ目"}]}
    documents = [doc("c-1", "custom/c-1.yaml", kind="custom", data=value)]
    real_index.serve("custom", IndexSource(documents=rows, docs={None: documents}))
    env = make_server(real_index)
    content = "id: c-1\nname: カスタム 1\nsteps:\n  - text: 修正後\n"
    # 実行
    response = env.client.post(
        URL.format(source="custom"), json={"path": "custom/c-1", "content": content}
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["fallback"] is True
    assert "## 手順" in data["markdown"]
    assert "カスタム変換" not in data["markdown"]


def test_error_when_not_found(body_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """無い文書を指すと 404 で何が無いかを返却する（異常系）。"""
    # 準備
    body_source(body_index)
    env = make_server(body_index)
    # 実行
    response = env.client.post(
        URL.format(source="sample"), json={"path": "no-such-doc", "content": "id: x\n"}
    )
    # 検証
    data = response.json()
    assert response.status_code == 404, data
    assert data["missing"] == "doc"
    assert data["value"] == "no-such-doc"
