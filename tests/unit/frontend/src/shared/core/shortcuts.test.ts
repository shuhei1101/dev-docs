import { expect, test } from "vitest";

import { shortcutsFor } from "@/shared/core/shortcuts";

const summarize = (
  screen: "doc-view" | "settings" | "not-found",
  singleKey: boolean,
) =>
  shortcutsFor(screen, singleKey).map(({ def, hotkeys }) => [def.id, hotkeys]);

test("test_shortcuts_for", () => {
  expect(summarize("doc-view", true)).toEqual([
    ["search", ["Mod+K", "/"]],
    ["help", ["Shift+/"]],
  ]);
});

test("test_shortcuts_for_when_single_key_off", () => {
  expect(summarize("doc-view", false)).toEqual([["search", ["Mod+K"]]]);
});

test("test_shortcuts_for_when_settings", () => {
  expect(summarize("settings", true)).toEqual([["help", ["Shift+/"]]]);
});
