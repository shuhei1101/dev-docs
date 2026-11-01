import { expect, test } from "vitest";

import { servingSources } from "@/features/docs/shared/serving-sources";
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
