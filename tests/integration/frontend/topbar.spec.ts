import { type Page, expect, test } from "@playwright/test";

import { axeViolations, openStory } from "./support/storybook";

const bar = (page: Page) => page.getByRole("banner");

const noHorizontalScroll = (page: Page) =>
  page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );

test.describe("DocView", () => {
  // 文書の画面。配信元 3 件・リビジョン・コメント 2 件を出す（正常系）
  test("doc_view", async ({ page }) => {
    // 準備・実行
    await openStory(page, "layout-topbar--doc-view");
    // 検証
    await expect(bar(page).getByRole("button", { name: "配信元を切り替える。今は sample" })).toBeVisible();
    await expect(bar(page).getByRole("button", { name: "リビジョンを切り替える。今は develop" })).toBeVisible();
    const search = bar(page).getByRole("button", { name: "検索 Ctrl K" });
    await expect(search).toHaveAttribute("aria-keyshortcuts", "Control+K /");
    await expect(search.locator("kbd")).toHaveText("Ctrl K");
    const comment = bar(page).getByRole("button", { name: "コメント 2 件" });
    await expect(comment).toContainText("2");
    await expect(bar(page).getByLabel("設定", { exact: true })).toBeVisible();
    await expect(bar(page).getByRole("button", { name: "文書の一覧を開く" })).toBeHidden();
    expect(await axeViolations(page)).toEqual([]);
  });

  // 配信元のメニューに 3 件を並べ、書き込み権限を添えて今の項目に aria-current を付ける（正常系）
  test("doc_view_source_menu", async ({ page }) => {
    await openStory(page, "layout-topbar--doc-view");
    await bar(page).getByRole("button", { name: /配信元を切り替える/ }).click();
    const items = page.getByRole("menuitem");
    await expect(items).toHaveCount(3);
    await expect(items.filter({ hasText: "sample" })).toContainText("読み書き");
    await expect(items.filter({ hasText: "knowledge" })).toContainText("読み取りだけ");
    await expect(items.filter({ hasText: "sample" })).toHaveAttribute("aria-current", "true");
  });

  // リビジョンのメニューにブランチ・タグ・最近の commit・比較を並べる（正常系）
  test("doc_view_ref_menu", async ({ page }) => {
    await openStory(page, "layout-topbar--doc-view");
    await bar(page).getByRole("button", { name: /リビジョンを切り替える/ }).click();
    await expect(page.getByRole("menuitem", { name: "develop" })).toHaveAttribute("aria-current", "true");
    await expect(page.getByRole("menuitem", { name: "feat/frontend/react-spa" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "v0.1.0" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /8b1d4e0/ })).toContainText("docs: 文書を追加");
    await expect(page.getByRole("menuitem", { name: "別のリビジョンと比較" })).toBeVisible();
  });

  // メニューをキーボードだけで開閉し、Esc で閉じてボタンへフォーカスを戻す（正常系）
  test("doc_view_menu_keyboard", async ({ page }) => {
    await openStory(page, "layout-topbar--doc-view");
    const button = bar(page).getByRole("button", { name: /配信元を切り替える/ });
    await button.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("menu")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toHaveCount(0);
    await expect(button).toBeFocused();
  });
});

test.describe("DocViewNarrow", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // 場所の幅が 48rem 未満。サイドバーを開くボタンを出し、リビジョンと画面名をアイコンだけにする（正常系）
  test("doc_view_narrow", async ({ page }) => {
    await openStory(page, "layout-topbar--doc-view-narrow");
    await expect(bar(page).getByRole("button", { name: "文書の一覧を開く" })).toBeVisible();
    await expect(bar(page).getByText("dev-docs", { exact: true })).not.toBeInViewport();
    await expect(bar(page).getByText("develop", { exact: true })).toBeHidden();
    await expect(bar(page).getByRole("button", { name: /リビジョンを切り替える/ })).toBeVisible();
    expect(await noHorizontalScroll(page)).toBe(true);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("DocViewNoComments", () => {
  // コメントが 0 件で、件数を出さない（正常系）
  test("doc_view_no_comments", async ({ page }) => {
    await openStory(page, "layout-topbar--doc-view-no-comments");
    const comment = bar(page).getByRole("button", { name: "コメント 0 件" });
    await expect(comment).toBeVisible();
    await expect(comment).not.toContainText("0");
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("NonGitSource", () => {
  // Git 管理外の配信元。リビジョンのボタンを出さない（正常系）
  test("non_git_source", async ({ page }) => {
    await openStory(page, "layout-topbar--non-git-source");
    await expect(bar(page).getByRole("button", { name: "配信元を切り替える。今は notes" })).toBeVisible();
    await expect(bar(page).getByRole("button", { name: /リビジョンを切り替える/ })).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("Settings", () => {
  // 設定画面。画面名と明暗のボタンだけを出す（正常系）
  test("settings", async ({ page }) => {
    await openStory(page, "layout-topbar--settings");
    await expect(bar(page).getByRole("button")).toHaveCount(1);
    await expect(bar(page).getByRole("button", { name: "明暗を固定する" })).toBeVisible();
    await expect(bar(page).getByText("設定", { exact: true })).toBeVisible();
    await expect(bar(page).getByRole("link", { name: "dev-docs" })).toBeVisible();
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("NotFound", () => {
  // 見つからない画面。コメントを出さない（正常系）
  test("not_found", async ({ page }) => {
    await openStory(page, "layout-topbar--not-found");
    await expect(bar(page).getByRole("button", { name: /^コメント/ })).toHaveCount(0);
    await expect(bar(page).getByRole("button", { name: /配信元を切り替える/ })).toBeVisible();
    await expect(bar(page).getByRole("button", { name: /リビジョンを切り替える/ })).toBeVisible();
    await expect(bar(page).getByRole("button", { name: /^検索/ })).toBeVisible();
    await expect(bar(page).getByRole("button", { name: "文書の一覧を開く" })).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("NotFoundNarrow", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // 見つからない画面を幅 48rem 未満の場所に置く（正常系）
  test("not_found_narrow", async ({ page }) => {
    await openStory(page, "layout-topbar--not-found-narrow");
    await expect(bar(page).getByRole("button", { name: "文書の一覧を開く" })).toHaveCount(0);
    await expect(bar(page).getByRole("button", { name: /^検索/ })).toBeVisible();
    expect(await noHorizontalScroll(page)).toBe(true);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("NotFoundWithoutSource", () => {
  // 無い配信元を開いた見つからない画面。配信元のボタンに今の配信元を出さず、リビジョンのボタンを出さない（正常系）
  test("not_found_without_source", async ({ page }) => {
    await openStory(page, "layout-topbar--not-found-without-source");
    const source = bar(page).getByRole("button", { name: "配信元を切り替える" });
    await expect(source).toBeVisible();
    await expect(source).toContainText("配信元");
    await expect(bar(page).getByRole("button", { name: /リビジョンを切り替える/ })).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("DarkScheme", () => {
  // 明暗を暗に固定した状態。明暗のボタンが押した状態になる（正常系）
  test("dark_scheme", async ({ page }) => {
    await openStory(page, "layout-topbar--dark-scheme");
    await expect(bar(page).getByRole("button", { name: "明暗を固定する" })).toHaveAttribute("aria-pressed", "true");
    expect(await axeViolations(page)).toEqual([]);
  });
});
