import { expect, test } from "vitest";

import { clampSidebarWidth } from "@/shared/stores/preferences";

test("test_clamp_sidebar_width", () => {
  expect([100, 300.4, 999].map(clampSidebarWidth)).toEqual([192, 300, 480]);
});
