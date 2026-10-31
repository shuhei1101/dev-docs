import { defineConfig, devices } from "@playwright/test";

const SCREEN_PORT = 5199;
const STORYBOOK_PORT = 6199;
const reuse = process.env.DEV_DOCS_REUSE_SERVER === "1";

export const SCREEN_URL = `http://127.0.0.1:${SCREEN_PORT}`;
export const STORYBOOK_URL = `http://127.0.0.1:${STORYBOOK_PORT}`;

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  reporter: "list",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: SCREEN_URL,
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
    viewport: { width: 1280, height: 800 },
    permissions: ["clipboard-read", "clipboard-write"],
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `npx vite --config frontend/vite.config.ts --host 127.0.0.1 --port ${SCREEN_PORT} --strictPort`,
      url: SCREEN_URL,
      cwd: "../../..",
      reuseExistingServer: reuse,
      timeout: 120_000,
    },
    {
      command: `npx storybook dev -c frontend/.storybook --host 127.0.0.1 -p ${STORYBOOK_PORT} --ci --no-open`,
      url: STORYBOOK_URL,
      cwd: "../../..",
      reuseExistingServer: reuse,
      timeout: 240_000,
    },
  ],
});
