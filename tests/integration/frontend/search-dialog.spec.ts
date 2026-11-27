import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { mockApi } from "./support/api-mock";
import { axeViolations, openStory } from "./support/storybook";

/** 本物の project-index（2588d67）を相手にした画面の検索の結合テストが確かめた応答 */
const matchCountResponse: unknown = JSON.parse(
  readFileSync(new URL("./support/search-match-count.json", import.meta.url), "utf8"),
);

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
  // 2 件に一致し、1 件目を選んだ状態。区切り線の行に名前・一致 N 行・パス・一致した箇所を出し、一致した単語を強調する（正常系）
  test("results", async ({ page }) => {
    await openStory(page, "docs-searchdialog--results");
    const status = dialog(page).getByRole("status");
    await expect(status).toHaveText("2 件（リビジョン develop）");
    const options = dialog(page).getByRole("option");
    await expect(options).toHaveCount(2);
    await expect(options.first()).toHaveAttribute("aria-selected", "true");
    await expect(options.first().locator("mark")).toHaveText("ページング");
    await expect(options.first()).toContainText("一致 9 行");
    await expect(options.first()).toContainText("docs/design/paging");
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
      dialog(page).getByRole("switch", { name: "配信元の設定で検索から除外した文書も含める" }),
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
      dialog(page).getByRole("switch", { name: "配信元の設定で検索から除外した文書も含める" }),
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
    const toggle = dialog(page).getByRole("switch", { name: "配信元の設定で検索から除外した文書も含める" });
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
      "該当する文書はありません。配信元の設定で検索から除外した文書を含めると 1 件あります。",
    );
    await expect(dialog(page).getByRole("option")).toHaveCount(0);
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("ProjectIndexUnreachable", () => {
  // project-index につながらず 503 を返却し、detail（アドレスと理由）を件数の文言に出す（異常系）
  test("project_index_unreachable", async ({ page }) => {
    await openStory(page, "docs-searchdialog--project-index-unreachable");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "project-index（http://127.0.0.1:8786）に接続できませんでした。接続を拒否されました（Connection refused）",
    );
    await expect(dialog(page).getByRole("option")).toHaveCount(0);
  });
});

test.describe("ManyResults", () => {
  // 一覧の高さを超える 30 件。一覧の中で縦にスクロールして 30 件目まで参照でき、一致した行の数の多い順に並ぶ（正常系）
  test("many_results", async ({ page }) => {
    await openStory(page, "docs-searchdialog--many-results");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "30 件（リビジョン develop）",
    );
    const options = dialog(page).getByRole("option");
    await expect(options).toHaveCount(30);
    await expect(options.first()).toContainText("一致 42 行");
    const list = dialog(page).locator("[cmdk-list]");
    const scrollable = await list.evaluate(
      (element) => element.scrollHeight > element.clientHeight,
    );
    expect(scrollable).toBe(true);
    await options.last().scrollIntoViewIfNeeded();
    await expect(options.last()).toBeInViewport();
    const box = await dialog(page).boundingBox();
    expect(box?.y ?? 0).toBeLessThan(100);
  });
});

test.describe("SortedByName", () => {
  // 並び順に「名前」を選ぶと、結果が名前の順に並ぶ（正常系）
  test("sorted_by_name", async ({ page }) => {
    await openStory(page, "docs-searchdialog--sorted-by-name");
    await expect(
      dialog(page).getByRole("radio", { name: "名前" }),
    ).toBeChecked();
    const names = await dialog(page)
      .getByRole("option")
      .evaluateAll((items) =>
        items.map((item) => item.querySelector("span span")?.textContent ?? ""),
      );
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, "ja")));
  });

  // 範囲と並び順の切り替えは矢印キーで選び直せる（正常系）
  test("sorted_by_name_keyboard", async ({ page }) => {
    await openStory(page, "docs-searchdialog--many-results");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "30 件（リビジョン develop）",
    );
    const matches = dialog(page).getByRole("radio", { name: "一致した行の数" });
    await matches.focus();
    await page.keyboard.press("ArrowRight");
    await expect(
      dialog(page).getByRole("radio", { name: "名前" }),
    ).toBeChecked();
  });
});

test.describe("WithoutMatchCount", () => {
  // matchCount が null の結果は「一致 N 行」を出さず、名前の順に並ぶ（正常系）
  test("without_match_count", async ({ page }) => {
    await openStory(page, "docs-searchdialog--without-match-count");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "2 件（リビジョン develop）",
    );
    const options = dialog(page).getByRole("option");
    await expect(options.first()).toContainText("インデックス");
    await expect(dialog(page).getByText(/一致 \d+ 行/)).toHaveCount(0);
  });
});

test.describe("AllSources", () => {
  // 全ての配信元を検索し、行に配信元の ID のバッジを出す。件数の文言にリビジョンを出さない（正常系）
  test("all_sources", async ({ page }) => {
    await openStory(page, "docs-searchdialog--all-sources");
    await expect(
      dialog(page).getByRole("radio", { name: "全ての配信元" }),
    ).toBeChecked();
    await expect(dialog(page).getByRole("status")).toHaveText("3 件");
    await expect(
      dialog(page).getByRole("option").filter({ hasText: "ページングのメモ" }),
    ).toContainText("notes");
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("AllSourcesPartialFailure", () => {
  // 配信していない配信元を「検索できなかった配信元」に理由つきで並べ、ほかの配信元の結果を出す（異常系）
  test("all_sources_partial_failure", async ({ page }) => {
    await openStory(page, "docs-searchdialog--all-sources-partial-failure");
    const failures = dialog(page).getByRole("list", {
      name: "検索できなかった配信元",
    });
    await expect(failures).toContainText("broken");
    await expect(failures).toContainText(
      "project-index が起動時の検証で除外しました。",
    );
    await expect(dialog(page).getByRole("option")).toHaveCount(3);
  });
});

test.describe("AllSourcesPending", () => {
  // 応答を待っている配信元があるとき、返却された結果を先に出し、件数の文言に検索中を続ける（正常系）
  test("all_sources_pending", async ({ page }) => {
    await openStory(page, "docs-searchdialog--all-sources-pending");
    await expect(dialog(page).getByRole("status")).toHaveText(
      "2 件・1 件の配信元を検索しています",
    );
    await expect(dialog(page).getByRole("option")).toHaveCount(2);
  });
});

test.describe("AllSourcesSearchFailed", () => {
  // 配信中の配信元の検索が 503 のとき、その配信元を detail つきで並べ、ほかの配信元の結果を出す（異常系）
  test("all_sources_search_failed", async ({ page }) => {
    await openStory(page, "docs-searchdialog--all-sources-search-failed");
    const failures = dialog(page).getByRole("list", {
      name: "検索できなかった配信元",
    });
    await expect(failures).toContainText("notes");
    await expect(failures).toContainText("応答がありませんでした（45 秒）");
    await expect(dialog(page).getByRole("status")).toHaveText("2 件");
    await expect(dialog(page).getByRole("option")).toHaveCount(2);
  });
});

test.describe("Mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // スマホの幅では画面いっぱいに開き、右上の閉じるボタンで閉じられる（正常系）
  test("mobile_full_screen", async ({ page }) => {
    await openStory(page, "docs-searchdialog--many-results");
    // 開くときの拡大のアニメーションを終えた大きさで比べる
    await expect
      .poll(async () => (await dialog(page).boundingBox())?.width)
      .toBe(390);
    await expect
      .poll(async () => (await dialog(page).boundingBox())?.height)
      .toBe(844);
    await expect(
      dialog(page).getByRole("button", { name: "閉じる" }),
    ).toBeVisible();
  });
});

test.describe("RealMatchCount", () => {
  // 本物の project-index の応答で、一致した行の数の多い順に並び、0 行の文書を含めて「一致 N 行」を出す（正常系）
  test("real_match_count", async ({ page }) => {
    // 準備
    await mockApi(page, { search: () => ({ body: matchCountResponse }) });
    await page.goto("/sample/docs/doc-1");
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    // 実行
    await page.getByRole("button", { name: /^検索/ }).click();
    await page.getByPlaceholder("文書を検索").fill("ページング");
    // 検証
    const options = dialog(page).getByRole("option");
    await expect(options).toHaveCount(3);
    await expect(options.nth(0)).toContainText("many");
    await expect(options.nth(0)).toContainText("一致 4 行");
    await expect(options.nth(1)).toContainText("one");
    await expect(options.nth(1)).toContainText("一致 1 行");
    await expect(options.nth(2)).toContainText("ページングの案内");
    await expect(options.nth(2)).toContainText("一致 0 行");
  });
});

