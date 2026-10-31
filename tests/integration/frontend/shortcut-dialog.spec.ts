import { type Page, expect, test } from "@playwright/test";

import { axeViolations, openStory } from "./support/storybook";

const dialog = (page: Page) =>
  page.getByRole("dialog", { name: "キーボードのショートカット" });

test.describe("DocView", () => {
  // 文書の画面のキーを出す。開いたとき閉じるボタンへフォーカスを移し、キーは kbd 要素で出す（正常系）
  test("doc_view", async ({ page }) => {
    await openStory(page, "layout-shortcutdialog--doc-view");
    await expect(dialog(page).getByText("検索を開く")).toBeVisible();
    await expect(dialog(page).getByText("ショートカットの一覧を開く")).toBeVisible();
    await expect(dialog(page).locator("kbd")).toHaveText(["Ctrl", "K", "/", "?"]);
    await expect(dialog(page).getByRole("button", { name: "閉じる" })).toBeFocused();
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("Settings", () => {
  // 設定画面のキーを出す(検索は出さない)（正常系）
  test("settings", async ({ page }) => {
    await openStory(page, "layout-shortcutdialog--settings");
    await expect(dialog(page).getByText("ショートカットの一覧を開く")).toBeVisible();
    await expect(dialog(page).getByText("検索を開く")).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("NotFound", () => {
  // 見つからない画面のキーを出す（正常系）
  test("not_found", async ({ page }) => {
    await openStory(page, "layout-shortcutdialog--not-found");
    await expect(dialog(page).getByText("検索を開く")).toBeVisible();
    await expect(dialog(page).getByText("ショートカットの一覧を開く")).toBeVisible();
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("SingleKeyOff", () => {
  // 1 文字のショートカットを切った状態。`Ctrl K` だけを出す（正常系）
  test("single_key_off", async ({ page }) => {
    await openStory(page, "layout-shortcutdialog--single-key-off");
    await expect(dialog(page).locator("kbd")).toHaveText(["Ctrl", "K"]);
    await expect(dialog(page).getByText("ショートカットの一覧を開く")).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});
