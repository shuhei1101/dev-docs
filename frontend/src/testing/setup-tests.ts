import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom は相対 URL の fetch を解けないため、画面のオリジンに直す
const originalFetch = globalThis.fetch;
globalThis.fetch = (input, init) =>
  originalFetch(typeof input === "string" && input.startsWith("/") ? new URL(input, window.location.origin) : input, init);

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
});
