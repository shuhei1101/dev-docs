import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useDelayedFlag } from "@/shared/hooks/use-delayed-flag";

const DELAY_MS = 300;

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

test("test_use_delayed_flag", () => {
  const { result } = renderHook(() => useDelayedFlag(true, DELAY_MS));

  act(() => vi.advanceTimersByTime(DELAY_MS - 1));
  expect(result.current).toBe(false);

  act(() => vi.advanceTimersByTime(1));
  expect(result.current).toBe(true);
});

test("test_use_delayed_flag_when_finished", () => {
  const { result, rerender } = renderHook(({ active }) => useDelayedFlag(active, DELAY_MS), {
    initialProps: { active: true },
  });

  act(() => vi.advanceTimersByTime(DELAY_MS - 1));
  rerender({ active: false });
  act(() => vi.advanceTimersByTime(DELAY_MS));

  expect(result.current).toBe(false);
});
