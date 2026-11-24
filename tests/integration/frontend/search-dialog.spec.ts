import { expect, test } from "@playwright/test";

import { axeViolations, openStory } from "./support/storybook";

const dialog = (page: import("@playwright/test").Page) =>
  page.getByRole("dialog", { name: "文書を検索" });

test.describe("Empty", () => {
  // 開いた直後。検索の単語が無く、結果の場所に何も出さない（正常系）
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
  // 2 件に一致し、1 件目を選んだ状態。一致した単語を強調する（正常系）
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
  // 一致が 0 件。`該当する文書はありません。別の条件を試してください。` を出す（正常系）
  test("no_results", async ({ page }) => {
    await openStory(page, "docs-searchdialog--no-results");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "該当する文書はありません。別の条件を試してください。",
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
  // 画面の検索がエラーを返却し、Problem Details の detail を結果の場所に出す（異常系）
  test("failed", async ({ page }) => {
    await openStory(page, "docs-searchdialog--failed");
    await expect(dialog(page).getByRole("status")).toHaveText("検索する単語が正しくありません");
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

test.describe("ExcludedCount", () => {
  // 一致した文書のうち検索から除外される文書を結果から除き、件数の後ろに除外した件数を出す（正常系）
  test("excluded_count", async ({ page }) => {
    await openStory(page, "docs-searchdialog--excluded-count");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "2 件（リビジョン develop）・検索から除外 1 件",
    );
    await expect(dialog(page).getByRole("option")).toHaveCount(2);
    await expect(
      dialog(page).getByRole("switch", { name: "検索から除外した文書も含める" }),
    ).toHaveAttribute("aria-checked", "false");
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("IncludeExcluded", () => {
  // スイッチを入れると検索から除外される文書も並び、その結果だけに `検索から除外` のバッジを付ける（正常系）
  test("include_excluded", async ({ page }) => {
    await openStory(page, "docs-searchdialog--include-excluded");
    const options = dialog(page).getByRole("option");
    await expect(
      dialog(page).getByRole("switch", { name: "検索から除外した文書も含める" }),
    ).toHaveAttribute("aria-checked", "true");
    await expect(options).toHaveCount(3);
    await expect(dialog(page).getByRole("status")).toHaveText("3 件（リビジョン develop）");
    await expect(options.filter({ hasText: "検索から除外" })).toHaveCount(1);
    await expect(options.filter({ hasText: "検索から除外" })).toContainText("旧ページング");
    expect(await axeViolations(page)).toEqual([]);
  });

  // スイッチは Tab で移り、Space で切り替える（正常系）
  test("include_excluded_keyboard", async ({ page }) => {
    await openStory(page, "docs-searchdialog--excluded-count");
    const toggle = dialog(page).getByRole("switch", { name: "検索から除外した文書も含める" });
    await toggle.focus();
    await page.keyboard.press("Space");
    await expect(toggle).toHaveAttribute("aria-checked", "true");
  });
});

test.describe("OnlyExcludedMatched", () => {
  // 一致した文書が全て検索から除外される文書のとき、含めた場合の件数を案内する（正常系）
  test("only_excluded_matched", async ({ page }) => {
    await openStory(page, "docs-searchdialog--only-excluded-matched");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "該当する文書はありません。検索から除外した文書を含めると 1 件あります。",
    );
    await expect(dialog(page).getByRole("option")).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});
