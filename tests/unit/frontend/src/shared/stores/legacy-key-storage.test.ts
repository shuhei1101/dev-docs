import { beforeEach, expect, test } from "vitest";

import { legacyKeyStorage } from "@/shared/stores/legacy-key-storage";

const NAME = "dev-docs:v1:shared:preferences";
const LEGACY = "dev-docs:preferences";

beforeEach(() => {
  localStorage.clear();
});

test("test_legacy_key_storage_when_legacy", () => {
  localStorage.setItem(LEGACY, '{"state":{"colorScheme":"dark"},"version":1}');

  const value = legacyKeyStorage(() => localStorage, LEGACY).getItem(NAME);

  expect(value).toBe('{"state":{"colorScheme":"dark"},"version":1}');
  expect(localStorage.getItem(NAME)).toBe('{"state":{"colorScheme":"dark"},"version":1}');
  expect(localStorage.getItem(LEGACY)).toBeNull();
});

test("test_legacy_key_storage_when_both", () => {
  localStorage.setItem(NAME, "new");
  localStorage.setItem(LEGACY, "old");

  const value = legacyKeyStorage(() => localStorage, LEGACY).getItem(NAME);

  expect(value).toBe("new");
  expect(localStorage.getItem(LEGACY)).toBe("old");
});

test("test_legacy_key_storage_when_empty", () => {
  const value = legacyKeyStorage(() => localStorage, LEGACY).getItem(NAME);

  expect(value).toBeNull();
});
