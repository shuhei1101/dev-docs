import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useMediaQuery } from "@/shared/hooks/use-media-query";

const QUERY = "(max-width: 47.99rem)";

/** `matches` を書き換えて `change` を手で送れる `matchMedia` の偽物 */
const stubMatchMedia = (initial: boolean) => {
  const listeners = new Set<() => void>();
  const state = { matches: initial };
  vi.stubGlobal("matchMedia", (media: string) => ({
    media,
    get matches() {
      return state.matches;
    },
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
  }));
  return {
    change: (matches: boolean) => {
      state.matches = matches;
      for (const listener of listeners) listener();
    },
  };
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("test_use_media_query", () => {
  stubMatchMedia(true);

  const { result } = renderHook(() => useMediaQuery(QUERY));

  expect(result.current).toBe(true);
});

test("test_use_media_query_when_changed", () => {
  const media = stubMatchMedia(true);
  const { result } = renderHook(() => useMediaQuery(QUERY));

  act(() => media.change(false));

  expect(result.current).toBe(false);
});
