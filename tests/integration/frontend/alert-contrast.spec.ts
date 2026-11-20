import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { openStory } from "./support/storybook";

const ALERT = '[data-slot="alert"]';

/** エラーのアラートの中の文字と背景が満たさない axe の color-contrast の違反の id */
const contrastViolations = async (page: Page) => {
  const result = await new AxeBuilder({ page })
    .include(ALERT)
    .withRules(["color-contrast"])
    .analyze();
  return result.violations.map((violation) => violation.id);
};

/** ダークのテーマで開くストーリーの id */
const dark = (id: string) => `${id}&globals=theme:dark`;

const STORIES = [
  {
    name: "alert_destructive",
    id: "shared-ui-alert--destructive",
    text: "本文を変換できませんでした",
  },
  {
    name: "alert_destructive_dark",
    id: "shared-ui-alert--destructive-dark",
    text: "本文を変換できませんでした",
  },
  {
    name: "alert_destructive_message_only",
    id: "shared-ui-alert--destructive-message-only",
    text: "配信元を削除できませんでした",
  },
  {
    name: "project_index_unreachable_alert",
    id: "shared-projectindexunreachablealert--unreachable",
    text: "project-index に接続できませんでした",
  },
  {
    name: "project_index_unreachable_alert_dark",
    id: dark("shared-projectindexunreachablealert--unreachable"),
    text: "project-index に接続できませんでした",
  },
  {
    name: "doc_view_conversion_error",
    id: "docs-docviewscreen--conversion-error",
    text: "本文を変換できませんでした",
  },
  {
    name: "doc_view_conversion_error_dark",
    id: dark("docs-docviewscreen--conversion-error"),
    text: "本文を変換できませんでした",
  },
];

for (const story of STORIES) {
  // エラーのアラートの見出し・説明・一覧・ボタンの文字が、背景とのコントラストの基準を満たす（正常系）
  test(story.name, async ({ page }) => {
    await openStory(page, story.id);
    const alert = page.locator(ALERT);
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(story.text);
    expect(await contrastViolations(page)).toEqual([]);
  });
}
