import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom は相対 URL の fetch を解けないため、画面のオリジンに直す
const originalFetch = globalThis.fetch;
globalThis.fetch = (input, init) =>
  originalFetch(
    typeof input === "string" && input.startsWith("/")
      ? new URL(input, window.location.origin)
      : input,
    init,
  );

// jsdom に無い API
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
  onchange: null,
})) as typeof window.matchMedia;
window.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
window.IntersectionObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
} as unknown as typeof IntersectionObserver;
Element.prototype.scrollIntoView ??= () => {};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
});
