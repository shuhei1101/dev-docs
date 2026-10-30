import { expect, test } from "vitest";

import {
  applySource,
  removeSource,
  sourceFormSchema,
  toFormValues,
} from "@/features/settings/settings/form";

const row = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  config: [`/home/me/${id}/dev-docs.yaml`],
  enabled: true,
  scope: { read: ["/home/me/**"], write: null },
  status: "serving",
  errors: [],
  configVersion: null,
  ...overrides,
});

const values = (overrides: Record<string, unknown> = {}) => ({
  id: "extra",
  config: "/a/dev-docs.yaml\n/a/local.yaml",
  enabled: true,
  read: "~/repo/**",
  write: "",
  ...overrides,
});

test("test_source_form_schema", () => {
  expect(sourceFormSchema([]).safeParse(values()).success).toBe(true);
});

test("test_source_form_schema_when_duplicate_id", () => {
  const result = sourceFormSchema(["extra"]).safeParse(values());

  expect(result.success).toBe(false);
  const issue = result.error?.issues.find((item) => item.path[0] === "id");
  expect(issue?.message).toBe("配信元の ID extra は既に使われています。別の ID を入力してください。");
});

test("test_source_form_schema_when_blank_line", () => {
  const result = sourceFormSchema([]).safeParse(values({ read: "~/repo/**\n\n~/work/**" }));

  const issue = result.error?.issues.find((item) => item.path[0] === "read");
  expect(issue?.message).toBe("読み取りの範囲に空の行があります。空の行を削除してください。");
});

test("test_to_form_values", () => {
  const result = toFormValues(row("a", { config: ["/a.yaml", "/b.yaml"] }) as never);

  expect(result.config).toBe("/a.yaml\n/b.yaml");
  expect(result.write).toBe("");
});

test("test_apply_source", () => {
  const sources = [row("a")] as never;

  const result = applySource(sources, values(), null);

  expect(result).toHaveLength(2);
  expect(result[1]).toMatchObject({ id: "extra", config: ["/a/dev-docs.yaml", "/a/local.yaml"] });
  expect(result[0]).toMatchObject({ id: "a", config: ["/home/me/a/dev-docs.yaml"] });
  expect(result[0]).not.toHaveProperty("status");
});

test("test_apply_source_when_edit", () => {
  const sources = [row("a", { scope: { read: ["/x/**"], write: ["/x"] } })] as never;

  const result = applySource(sources, values({ id: "a", write: "" }), 0);

  expect(result[0].scope).not.toHaveProperty("write");
});

test("test_remove_source", () => {
  const result = removeSource([row("a"), row("b")] as never, 0);

  expect(result.map((item) => item.id)).toEqual(["b"]);
});
