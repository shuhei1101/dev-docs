import assert from "node:assert/strict";
import { test } from "node:test";

import {
  fitIssueUrl,
  ISSUE_TRUNCATED,
  ISSUE_URL_MAX,
  shortenQuote,
} from "../../../../src/dev_docs/server/static/comments.js";

test("test_shorten_quote", () => {
  // 長い引用（正常系）
  // 準備
  const text = "abcdefghijklmnopqrstuvwxyz0123456789ABCD";
  // 実行
  const result = shortenQuote(text);
  // 検証
  assert.equal(result, "abcdefghijkl…23456789ABCD");
});

test("test_fit_issue_url", () => {
  // 長い本文の切り詰め（正常系）
  // 準備
  const body = "あ".repeat(20000);
  // 実行
  const url = fitIssueUrl("owner/name", ["docs"], "タイトル", body);
  // 検証
  assert.ok(url.length <= ISSUE_URL_MAX);
  assert.ok(new URL(url).searchParams.get("body")?.endsWith(ISSUE_TRUNCATED));
});

test("test_fit_issue_url_when_short", () => {
  // 収まる本文（正常系）
  // 準備
  const body = "x".repeat(100);
  // 実行
  const url = fitIssueUrl("owner/name", ["docs"], "タイトル", body);
  // 検証
  assert.equal(new URL(url).searchParams.get("body"), body);
});
