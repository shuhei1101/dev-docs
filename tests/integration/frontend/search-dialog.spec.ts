import { expect, test } from "@playwright/test";

import { axeViolations, openStory } from "./support/storybook";

const dialog = (page: import("@playwright/test").Page) =>
  page.getByRole("dialog", { name: "文書を検索" });

test.describe("Empty", () => {
  // 開いた直後。語が無く、結果の場所に何も出さない（正常系）
  test("empty", async ({ page }) => {
    await openStory(page, "docs-searchdialog--empty");
    const input = dialog(page).getByRole("combobox");
    await expect(input).toBeVisible();
    await expect(input).toHaveValue("");
    await expect(dialog(page).getByRole("option")).toHaveCount(0);
    await expect(dialog(page).locator('[role="status"]')).toHaveText("");
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("Results", () => {
  // 2 件に一致し、1 件目を選んだ状態。一致した語を強調する（正常系）
  test("results", async ({ page }) => {
    await openStory(page, "docs-searchdialog--results");
    const status = dialog(page).getByRole("status");
    await expect(status).toHaveText("2 件（リビジョン develop）");
    const options = dialog(page).getByRole("option");
    await expect(options).toHaveCount(2);
    await expect(options.first()).toHaveAttribute("aria-selected", "true");
    await expect(options.first().locator("mark")).toHaveText("ページング");
    expect(await axeViolations(page)).toEqual([]);
  });

  // 検索欄は combobox で、結果の一覧と選んでいる結果を指し、↓ で結果を選ぶ（正常系）
  test("results_keyboard", async ({ page }) => {
    await openStory(page, "docs-searchdialog--results");
    await expect(dialog(page).getByRole("status")).toHaveText("2 件（リビジョン develop）");
    const input = dialog(page).getByRole("combobox");
    await expect(input).toHaveAttribute("aria-controls", /.+/);
    await expect(input).toHaveAttribute("aria-activedescendant", /.+/);
    const first = await input.getAttribute("aria-activedescendant");
    await page.keyboard.press("ArrowDown");
    await expect(input).not.toHaveAttribute("aria-activedescendant", first ?? "");
    await expect(dialog(page).getByRole("option").nth(1)).toHaveAttribute("aria-selected", "true");
  });
});

test.describe("NoResults", () => {
  // 一致が 0 件。`該当する文書はありません。別の語を試してください。` を出す（正常系）
  test("no_results", async ({ page }) => {
    await openStory(page, "docs-searchdialog--no-results");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "該当する文書はありません。別の語を試してください。",
    );
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("Loading", () => {
  // 検索の結果を待っている（正常系）
  test("loading", async ({ page }) => {
    await openStory(page, "docs-searchdialog--loading");
    await expect(dialog(page).getByRole("status")).toHaveText("検索しています");
    await expect(dialog(page).getByRole("option")).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("Failed", () => {
  // 画面の検索がエラーを返し、Problem Details の detail を結果の場所に出す（異常系）
  test("failed", async ({ page }) => {
    await openStory(page, "docs-searchdialog--failed");
    await expect(dialog(page).getByRole("status")).toHaveText("検索する語が正しくありません");
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("NonGitSource", () => {
  // Git 管理外の配信元。件数の文言にリビジョンを出さない（正常系）
  test("non_git_source", async ({ page }) => {
    await openStory(page, "docs-searchdialog--non-git-source");
    await expect(dialog(page).getByRole("status")).toHaveText("2 件");
    expect(await axeViolations(page)).toEqual([]);
  });
});
