import { beforeEach, expect, test } from "vitest";

import {
  type PendingEdit,
  toCommitEdits,
  usePendingEditsStore,
} from "@/features/metadata/shared/pending-edits-store";

const edit = (overrides: Partial<PendingEdit> = {}): PendingEdit => ({
  key: "tags:n1:update",
  kind: "tags",
  op: "update",
  docId: "n1",
  docKind: "note",
  expectedVersion: "c3d4e5",
  docPath: "notes/n1.yaml",
  values: { tags: ["topic:a", "topic:b"] },
  before: { tags: ["topic:a"] },
  label: "タグ: n1",
  ...overrides,
});

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

test("test_to_commit_edits", () => {
  const edits = [
    edit(),
    edit({ key: "terms:kind:add", kind: "terms", op: "add", docId: "kind", docKind: "terms", expectedVersion: null, docPath: null, values: { name: "種類" }, before: {} }),
    edit({ key: "terms:old:delete", kind: "terms", op: "delete", docId: "old", docKind: "terms", expectedVersion: "b2", docPath: "glossary.yaml", values: {} }),
  ];

  const result = toCommitEdits(edits);

  expect(result).toEqual([
    { key: "tags:n1:update", kind: "tags", op: "update", docId: "n1", docKind: "note", expectedVersion: "c3d4e5", docPath: "notes/n1.yaml", values: { tags: ["topic:a", "topic:b"] } },
    { key: "terms:kind:add", kind: "terms", op: "add", docId: "kind", docKind: "terms", values: { name: "種類" } },
    { key: "terms:old:delete", kind: "terms", op: "delete", docId: "old", docKind: "terms", expectedVersion: "b2", values: {} },
  ]);
});

test("test_upsert", () => {
  const { upsert } = usePendingEditsStore.getState();

  upsert("sample", edit({ values: { tags: ["topic:b"] } }), "aaa1111");
  upsert("sample", edit({ values: { tags: ["topic:c"] } }), "aaa1111");
  const afterSecond = usePendingEditsStore.getState().bySource.sample;
  upsert("sample", edit({ values: { tags: ["topic:a"] } }), "aaa1111");

  expect(afterSecond).toHaveLength(1);
  expect(afterSecond?.[0]?.values).toEqual({ tags: ["topic:c"] });
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});

test("test_upsert_when_base_commit", () => {
  const { upsert, remove } = usePendingEditsStore.getState();

  upsert("sample", edit(), "aaa1111");
  upsert("sample", edit({ key: "tags:n2:update", docId: "n2" }), "bbb2222");
  const afterSecond = usePendingEditsStore.getState().baseCommitBySource.sample;
  remove("sample", "tags:n1:update");
  remove("sample", "tags:n2:update");

  expect(afterSecond).toBe("aaa1111");
  expect(usePendingEditsStore.getState().baseCommitBySource.sample).toBeUndefined();
});

test("test_rebase", () => {
  const { upsert, rebase } = usePendingEditsStore.getState();
  upsert("sample", edit(), "aaa1111");
  upsert("sample", edit({ key: "tags:n2:update", docId: "n2" }), "aaa1111");

  const dropped = rebase("sample", "ccc3333", {
    tags: { n1: { tags: ["topic:a"] }, n2: { tags: ["topic:a"] } },
  });

  expect(dropped).toEqual([]);
  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
  expect(usePendingEditsStore.getState().baseCommitBySource.sample).toBe("ccc3333");
});

test("test_rebase_when_latest_changed", () => {
  const { upsert, rebase } = usePendingEditsStore.getState();
  upsert("sample", edit(), "aaa1111");
  upsert(
    "sample",
    edit({ key: "terms:kind:add", kind: "terms", op: "add", docId: "kind", docKind: "terms", expectedVersion: null, docPath: null, values: { name: "種類" }, before: {} }),
    "aaa1111",
  );

  const dropped = rebase("sample", "ccc3333", { tags: { n1: { tags: ["topic:x"] } } });

  expect(dropped.map((item) => item.key)).toEqual(["tags:n1:update"]);
  expect((usePendingEditsStore.getState().bySource.sample ?? []).map((item) => item.op)).toEqual(["add"]);
  expect(usePendingEditsStore.getState().baseCommitBySource.sample).toBe("ccc3333");
});
