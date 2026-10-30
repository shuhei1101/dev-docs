import { expect, test } from "vitest";

import { describeMissing } from "@/features/docs/not-found/missing";

test("test_describe_missing", () => {
  const result = describeMissing({ missing: "doc", value: "a.md" });

  expect(result.kind).toBe("doc");
  expect(result.details).toEqual([{ label: "開こうとしたパス", value: "a.md" }]);
});

test("test_describe_missing_when_not_served", () => {
  const result = describeMissing(
    {
      missing: "not_served",
      value: "broken",
      errors: [{ path: "documents[0]", reason: "必須" }],
    },
    { configs: ["/r/dev-docs.yaml"] },
  );

  expect(result.kind).toBe("not_served");
  expect(result.details).toContainEqual({ label: "外した理由", value: "documents[0] 必須" });
  expect(result.details).toContainEqual({ label: "設定ファイル", value: "/r/dev-docs.yaml" });
});

test("test_describe_missing_when_route", () => {
  expect(describeMissing(undefined).kind).toBe("route");
});

test("test_describe_missing_when_ref", () => {
  const result = describeMissing({ missing: "ref", value: "nope" }, { defaultRef: "main" });

  expect(result.kind).toBe("ref");
  expect(result.details).toContainEqual({ label: "開こうとしたリビジョン", value: "nope" });
  expect(result.details).toContainEqual({ label: "既定のリビジョン", value: "main" });
});
