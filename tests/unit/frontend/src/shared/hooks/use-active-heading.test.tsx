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
  vi.restoreAllMocks();
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

/** use-active-heading.ts の SETTLE_MARGIN と同じ値（px） */
const SETTLE_MARGIN = 48;

test("test_use_active_heading_when_scroll_margin", async () => {
  document.body.innerHTML = '<h2 id="a">A</h2><h2 id="b">B</h2>';
  const tops: Record<string, number> = { a: -100, b: SETTLE_MARGIN + 8 };
  const margins: Record<string, string> = { a: "0px", b: "56px" };
  for (const id of Object.keys(tops)) {
    const element = document.getElementById(id) as HTMLElement;
    element.getBoundingClientRect = () => ({ top: tops[id] }) as DOMRect;
  }
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => {
    const margin = margins[(element as HTMLElement).id] ?? "0px";
    return {
      scrollMarginTop: margin,
      getPropertyValue: (name: string) => (name === "scroll-margin-top" ? margin : ""),
    } as unknown as CSSStyleDeclaration;
  });
  const { result } = renderHook(() => useActiveHeading(["a", "b"], 0));

  const { act } = await import("@testing-library/react");
  act(() => {
    window.dispatchEvent(new Event("scroll"));
  });

  expect(result.current).toBe("b");
});
