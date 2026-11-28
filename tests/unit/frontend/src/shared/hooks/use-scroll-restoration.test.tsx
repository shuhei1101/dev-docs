import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useScrollRestoration } from "@/shared/hooks/use-scroll-restoration";

const KEY_A = "dev-docs:v1:doc-view:sidebar:s:0:scroll";
const KEY_B = "dev-docs:v1:doc-view:sidebar:s:1:scroll";
const KEY_NEW = "dev-docs:v1:doc-view:sidebar:s:2:scroll";

// jsdom は配置を計算せず `scrollTop` の書き込みを捨てるので、書き込んだ値を保つ
let scrollTop = 0;
const setScrollTop = vi.fn((value: number) => {
  scrollTop = value;
});
const element = document.createElement("div");
Object.defineProperty(element, "scrollTop", {
  get: () => scrollTop,
  set: setScrollTop,
  configurable: true,
});
const ref = { current: element };

const renderScroll = (key: string) =>
  renderHook(({ current }) => useScrollRestoration(ref, current), {
    initialProps: { current: key },
  });

beforeEach(() => {
  sessionStorage.clear();
  scrollTop = 0;
  setScrollTop.mockClear();
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 0;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("test_use_scroll_restoration_when_key_changed", () => {
  sessionStorage.setItem(KEY_B, "120");
  const { rerender } = renderScroll(KEY_A);
  scrollTop = 300;
  element.dispatchEvent(new Event("scroll"));

  rerender({ current: KEY_B });
  expect(element.scrollTop).toBe(120);

  rerender({ current: KEY_A });
  expect(element.scrollTop).toBe(300);
});

test("test_use_scroll_restoration_when_first_render", () => {
  sessionStorage.setItem(KEY_A, "480");

  renderScroll(KEY_A);

  expect(setScrollTop).not.toHaveBeenCalled();
});

test("test_use_scroll_restoration_when_new_key", () => {
  const { rerender } = renderScroll(KEY_A);
  scrollTop = 300;

  rerender({ current: KEY_NEW });

  expect(element.scrollTop).toBe(0);
});
