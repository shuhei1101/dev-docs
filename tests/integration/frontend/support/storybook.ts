import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const STORYBOOK = "http://127.0.0.1:6199";

/** Storybook のストーリーを、サイドバーなしの画面で開く */
export const openStory = async (page: Page, id: string): Promise<void> => {
  await page.goto(`${STORYBOOK}/iframe.html?id=${id}&viewMode=story`);
  await page.locator("#storybook-root > *, #storybook-root").first().waitFor({ state: "attached" });
};

const AXE_RETRY_LIMIT = 10;
const AXE_RETRY_WAIT_MS = 500;

/** ストーリーを単独で置いたために出る検出(ランドマークと見出し 1)を除いた axe の違反の id。Storybook の a11y アドオンが走っている間は待って取り直す */
export const axeViolations = async (page: Page): Promise<string[]> => {
  for (let attempt = 1; ; attempt += 1) {
    try {
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .disableRules(["landmark-one-main", "page-has-heading-one", "region"])
        .analyze();
      return result.violations.map((violation) => violation.id);
    } catch (error) {
      const running = error instanceof Error && error.message.includes("Axe is already running");
      if (!running || attempt >= AXE_RETRY_LIMIT) throw error;
      await page.waitForTimeout(AXE_RETRY_WAIT_MS);
    }
  }
};
