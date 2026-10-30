import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useActiveHeading } from "@/shared/hooks/use-active-heading";

type Callback = (entries: Partial<IntersectionObserverEntry>[]) => void;

let callbacks: Callback[] = [];

class FakeIntersectionObserver {
  constructor(callback: Callback) {
    callbacks.push(callback);
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  callbacks = [];
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
  document.body.innerHTML = '<h2 id="a">A</h2><h2 id="b">B</h2><h3 id="c">C</h3>';
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const crossed = (id: string) => ({
  target: document.getElementById(id) as Element,
  isIntersecting: false,
  boundingClientRect: { top: -50 } as DOMRectReadOnly,
});
const below = (id: string) => ({
  target: document.getElementById(id) as Element,
  isIntersecting: true,
  boundingClientRect: { top: 400 } as DOMRectReadOnly,
});

test("test_use_active_heading", async () => {
  const { result } = renderHook(() => useActiveHeading(["a", "b", "c"], 0));

  const { act } = await import("@testing-library/react");
  act(() => {
    for (const callback of callbacks) callback([crossed("a"), crossed("b"), below("c")]);
  });

  expect(result.current).toBe("b");
});

test("test_use_active_heading_when_empty", () => {
  const { result } = renderHook(() => useActiveHeading([], 0));

  expect(result.current).toBeNull();
});
