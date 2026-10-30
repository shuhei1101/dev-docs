import { expect, test } from "vitest";

import { describeMissing } from "@/features/docs/not-found/missing";

test("test_describe_missing", () => {
  const result = describeMissing({
    missing: { kind: "doc", source: "s", ref: "main", path: "a.md" },
  });

  expect(result.kind).toBe("doc");
  const values = result.details.map((detail) => detail.value);
  expect(values).toContain("a.md");
  expect(values).toContain("main");
});

test("test_describe_missing_when_not_served", () => {
  const result = describeMissing({
    missing: { kind: "not_served", source: "s" },
    errors: [{ path: "documents[0]", reason: "paths が必要です" }],
  });

  expect(result.kind).toBe("not_served");
});

test("test_describe_missing_when_route", () => {
  expect(describeMissing(undefined).kind).toBe("route");
});
