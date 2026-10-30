import { expect, test } from "vitest";

import {
  ISSUE_URL_MAX,
  TRUNCATED_NOTE,
  buildIssueUrl,
  formatComments,
} from "@/features/docs/shared/comments/comment-format";

const comment = (overrides: Record<string, unknown> = {}) => ({
  id: "1",
  docId: "s@main:a.md",
  source: "s",
  ref: "main",
  path: "a.md",
  docTitle: "A",
  headings: ["見出し1"],
  quote: "引用",
  prefix: "",
  suffix: "",
  body: "本文",
  selected: true,
  createdAt: "2026-10-26T14:40:00Z",
  ...overrides,
});

test("test_format_comments", () => {
  const text = formatComments([comment(), comment({ id: "2", headings: [], quote: "二行目\n三行目" })]);

  expect(text).toContain("A › 見出し1");
  expect(text).toContain("A › 冒頭");
  expect(text).toContain("> 引用");
  expect(text).toContain("> 二行目\n> 三行目");
});

test("test_build_issue_url", () => {
  const { url, truncated } = buildIssueUrl({ repository: "o/r", issueLabels: ["docs"] }, "短い本文");

  expect(truncated).toBe(false);
  const parsed = new URL(url);
  expect(parsed.origin + parsed.pathname).toBe("https://github.com/o/r/issues/new");
  expect(parsed.searchParams.get("labels")).toBe("docs");
  expect(parsed.searchParams.get("body")).toBe("短い本文");
});

test("test_build_issue_url_when_too_long", () => {
  const { url, truncated } = buildIssueUrl(
    { repository: "o/r", issueLabels: ["docs"] },
    "あ".repeat(10000),
  );

  expect(truncated).toBe(true);
  expect(url.length).toBeLessThanOrEqual(ISSUE_URL_MAX);
  expect(new URL(url).searchParams.get("body")?.endsWith(TRUNCATED_NOTE)).toBe(true);
});
