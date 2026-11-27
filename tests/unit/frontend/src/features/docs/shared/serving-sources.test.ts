import { expect, test } from "vitest";

import { servingSources, unservedSources } from "@/features/docs/shared/serving-sources";
import { settingsSource, settingsView } from "@tests/helpers/fixtures";

test("test_serving_sources", () => {
  const view = settingsView([settingsSource("s"), settingsSource("broken", { status: "error" })]);

  expect(servingSources(view as never)).toEqual([{ id: "s", writable: true }]);
});

test("test_serving_sources_when_write_scope", () => {
  const view = settingsView([
    settingsSource("a", { scope: { read: [], write: null } }),
    settingsSource("b", { scope: { read: [], write: [] } }),
    settingsSource("c", { scope: { read: [], write: ["docs/"] } }),
  ]);

  expect(servingSources(view as never).map((item) => item.writable)).toEqual([true, false, true]);
});

test("test_serving_sources_when_undefined", () => {
  expect(servingSources(undefined)).toEqual([]);
});

test("test_unserved_sources", () => {
  const view = settingsView([
    settingsSource("s"),
    settingsSource("broken", {
      status: "not_served",
      errors: [{ path: "documents[0]", reason: "paths は必須です" }],
    }),
    settingsSource("off", { status: "disabled" }),
  ]);

  const unserved = unservedSources(view as never);

  expect(unserved.map((item) => item.source)).toEqual(["broken"]);
  expect(unserved[0]?.reason).toContain("project-index が起動時の検証で除外しました。");
  expect(unserved[0]?.reason).toContain("documents[0] paths は必須です");
});

test("test_unserved_sources_when_undefined", () => {
  expect(unservedSources(undefined)).toEqual([]);
});
