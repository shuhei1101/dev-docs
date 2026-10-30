import { expect, test } from "vitest";

import { formatJst } from "@/shared/lib/format";

test("test_format_jst", () => {
  expect(formatJst("2026-10-26T14:40:00Z")).toBe("10/26 23:40 JST");
});

test("test_format_jst_when_date_changes", () => {
  expect(formatJst("2026-12-31T15:05:00Z")).toBe("01/01 00:05 JST");
});
