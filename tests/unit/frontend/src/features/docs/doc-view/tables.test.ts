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
    {
      key: "t2",
      marker: { start: 4, end: 4, text: "<!-- table: data +columns -->" },
      columns: true,
    },
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

const JSON_MARKDOWN = [
  '<!-- table: {"kind": "data", "features": {"columns": {}}} -->',
  "",
  "| 名前 | 備考 |",
  "| --- | --- |",
  "| x | y |",
  "",
  "<!-- /table -->",
  "",
  "<!-- table: {",
  '  "kind": "data", "columns": {"備考": {"hidden": true}}',
  "} -->",
  "",
  "| 名前 | 備考 |",
  "| --- | --- |",
  "| x | y |",
  "",
  "<!-- /table -->",
  "",
  '<!-- table: {"kind": "data", "features": {"columns": {"enabled": false}}, "columns": {"備考": {"hidden": true}}} -->',
  "",
  "| 名前 | 備考 |",
  "| --- | --- |",
  "| x | y |",
  "",
  "<!-- /table -->",
  "",
  '<!-- table: {"kind": "data"} -->',
  "",
  "| 名前 | 備考 |",
  "| --- | --- |",
  "| x | y |",
  "",
  "<!-- /table -->",
  "",
].join("\n");

test("test_find_tables_when_json_marker", () => {
  const tables = findTables({
    markdown: JSON_MARKDOWN,
    tableKeys: ["t1", "t2", "t3", "t4"],
  });

  expect(tables.map((table) => table.columns)).toEqual([true, true, false, false]);
  expect(tables[1].marker?.start).toBe(8);
  expect(tables[1].marker?.end).toBe(10);
});

/** 1 行の表のマーカーの JSON の引数を返す */
const markerArgs = (line: string): unknown =>
  JSON.parse(line.replace(/^<!--\s*table:\s*/, "").replace(/\s*-->\s*$/, ""));

test("test_apply_hidden_columns_when_json_marker", () => {
  const markdown = [
    "<!-- table: {",
    '  "kind": "data",',
    '  "columns": {"説明": {"hidden": true, "width": {"mode": "nowrap"}}}',
    "} -->",
    "",
    "| 名前 | 説明 | 備考 |",
    "| --- | --- | --- |",
    "| x | y | z |",
    "",
    "<!-- /table -->",
    "",
    '<!-- table: {"kind": "data", "columns": {"ID": {"hidden": true}}} -->',
    "",
    "| 表示 | ID |",
    "| --- | --- |",
    "| x | a |",
    "",
    "<!-- /table -->",
    "",
  ].join("\n");

  const result = applyHiddenColumns({
    markdown,
    tableKeys: ["t1", "t2"],
    columns: { t1: ["備考"], t2: [] },
  });
  const markers = result.split("\n").filter((line) => line.startsWith("<!-- table:"));

  expect(markers).toHaveLength(2);
  expect(markerArgs(markers[0])).toEqual({
    kind: "data",
    columns: { 説明: { width: { mode: "nowrap" } }, 備考: { hidden: true } },
  });
  expect(markerArgs(markers[1])).toEqual({ kind: "data", features: { columns: {} } });
});
