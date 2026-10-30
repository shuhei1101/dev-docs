import { expect, test } from "vitest";

import { splitHighlight } from "@/features/docs/shared/search-dialog/highlight";

test("test_split_highlight", () => {
  expect(splitHighlight("Foo bar foo", "foo bar")).toEqual([
    { text: "Foo", match: true },
    { text: " ", match: false },
    { text: "bar", match: true },
    { text: " ", match: false },
    { text: "foo", match: true },
  ]);
});

test("test_split_highlight_when_symbol", () => {
  const parts = splitHighlight("axb a.b", "a.b");

  expect(parts.filter((part) => part.match).map((part) => part.text)).toEqual([
    "a.b",
  ]);
  expect(parts.map((part) => part.text).join("")).toBe("axb a.b");
});
