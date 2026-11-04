import { expect, test } from "vitest";

import {
  applyHiddenColumns,
  columnTableKeys,
  findTables,
} from "@/features/docs/doc-view/tables";

const MARKDOWN = [
  "| a | b |",
  "| --- | --- |",
  "| 1 | 2 |",
  "",
  "<!-- table: data +columns -->",
  "",
  "| 名前 | 備考 |",
  "| --- | --- |",
  "| x | y |",
  "",
  "<!-- /table -->",
  "",
  "```",
  "| c | d |",
  "| --- | --- |",
  "```",
  "",
].join("\n");

test("test_find_tables", () => {
  const tables = findTables({ markdown: MARKDOWN, tableKeys: ["t1", "t2"] });

  expect(tables).toEqual([
    { key: "t1", marker: null, columns: false },
    { key: "t2", marker: { line: 4, text: "<!-- table: data +columns -->" }, columns: true },
  ]);
});

test("test_apply_hidden_columns", () => {
  const result = applyHiddenColumns({
    markdown: MARKDOWN,
    tableKeys: ["t1", "t2"],
    columns: { t1: ["a"], t2: ["備考"] },
  });

  expect(result.split("\n")[4]).toBe("<!-- table: data +columns hide=備考 -->");
  expect(result.split("\n").slice(0, 3)).toEqual(MARKDOWN.split("\n").slice(0, 3));
  expect(result).not.toContain("hide=a");
});

test("test_column_table_keys", () => {
  expect(columnTableKeys({ markdown: MARKDOWN, tableKeys: ["t1", "t2"] })).toEqual(["t2"]);
});
