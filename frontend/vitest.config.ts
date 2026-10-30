import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const root = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  root,
  plugins: [react()],
  resolve: {
    alias: {
      "@tests": fileURLToPath(new URL("../tests/unit/frontend", import.meta.url)),
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./frontend/src/testing/setup-tests.ts", "./tests/unit/frontend/setup-msw.ts"],
    include: ["tests/unit/frontend/**/*.test.{ts,tsx}"],
    coverage: {
      include: ["frontend/src/**"],
      exclude: ["frontend/src/routes/**", "frontend/src/shared/api/generated/**"],
    },
  },
});
