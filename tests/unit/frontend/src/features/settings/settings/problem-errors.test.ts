import { expect, test } from "vitest";

import { toFieldErrors } from "@/features/settings/settings/problem-errors";

test("test_to_field_errors", () => {
  const errors = [
    { path: "sources[1].config[0]", reason: "ファイルがありません" },
    { path: "sources[0].id", reason: "使えない文字があります" },
  ];

  const result = toFieldErrors(errors, 1);

  expect(result.fields).toEqual([{ name: "config", message: "ファイルがありません" }]);
  expect(result.summary).toHaveLength(2);
});
