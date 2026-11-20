import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { openStory } from "./support/storybook";

const ALERT = '[data-slot="alert"]';

const AXE_RETRY_LIMIT = 10;
const AXE_RETRY_WAIT_MS = 500;

/** エラーのアラートの中の文字と背景が満たさない axe の color-contrast の違反の id。Storybook の a11y アドオンが走っている間は待って再取得する */
const contrastViolations = async (page: Page): Promise<string[]> => {
  for (let attempt = 1; ; attempt += 1) {
    try {
      const result = await new AxeBuilder({ page })
        .include(ALERT)
        .withRules(["color-contrast"])
        .analyze();
      return result.violations.map((violation) => violation.id);
    } catch (error) {
      const running =
        error instanceof Error &&
        error.message.includes("Axe is already running");
      if (!running || attempt >= AXE_RETRY_LIMIT) throw error;
      await page.waitForTimeout(AXE_RETRY_WAIT_MS);
    }
  }
};

/** ダークのテーマで開くストーリーの id */
const dark = (id: string) => `${id}&globals=theme:dark`;

/** テーマごとの `html` の class */
const HTML_CLASS = { light: /^(?!.*\bdark\b)/, dark: /\bdark\b/ } as const;

const STORIES = [
  {
    name: "alert_destructive",
    id: "shared-ui-alert--destructive",
    theme: "light" as const,
    text: "本文を変換できませんでした",
  },
  {
    name: "alert_destructive_dark",
    id: "shared-ui-alert--destructive-dark",
    theme: "dark" as const,
    text: "本文を変換できませんでした",
  },
  {
    name: "alert_destructive_message_only",
    id: "shared-ui-alert--destructive-message-only",
    theme: "light" as const,
    text: "配信元を削除できませんでした",
  },
  {
    name: "project_index_unreachable_alert",
    id: "shared-projectindexunreachablealert--unreachable",
    theme: "light" as const,
    text: "project-index に接続できませんでした",
  },
  {
    name: "project_index_unreachable_alert_dark",
    id: dark("shared-projectindexunreachablealert--unreachable"),
    theme: "dark" as const,
    text: "project-index に接続できませんでした",
  },
  {
    name: "doc_view_conversion_error",
    id: "docs-docviewscreen--conversion-error",
    theme: "light" as const,
    text: "本文を変換できませんでした",
  },
  {
    name: "doc_view_conversion_error_dark",
    id: dark("docs-docviewscreen--conversion-error"),
    theme: "dark" as const,
    text: "本文を変換できませんでした",
  },
];

for (const story of STORIES) {
  // エラーのアラートの見出し・説明・一覧・ボタンの文字が、背景とのコントラストの基準を満たす（正常系）
  test(story.name, async ({ page }) => {
    await openStory(page, story.id);
    await expect(page.locator("html")).toHaveClass(HTML_CLASS[story.theme]);
    const alert = page.locator(ALERT);
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(story.text);
    expect(await contrastViolations(page)).toEqual([]);
  });
}
