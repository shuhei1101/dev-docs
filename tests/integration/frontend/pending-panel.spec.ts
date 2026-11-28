import { type Page, expect, test } from "@playwright/test";

import { boxOf, viewportOf } from "./support/geometry";
import { axeViolations, openStory } from "./support/storybook";

const panel = (page: Page) =>
  page.getByRole("dialog", { name: "レビュー中" }).or(page.getByRole("complementary", { name: "レビュー中" }));

const noHorizontalScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test.describe("MetadataEdits", () => {
  // メタデータの変更 3 件を、操作の種類・変更前と変更後・移動と取り消しのボタンと並べる（正常系）
  test("metadata_edits", async ({ page }) => {
    // 準備・実行
    await openStory(page, "layout-pendingpanel--metadata-edits");
    // 検証
    await expect(panel(page)).toContainText("sample の develop へ、3 件の変更をまとめてコミットします。");
    await expect(panel(page).getByRole("listitem")).toHaveCount(3);
    await expect(panel(page).getByRole("button", { name: "タグ: n1 の行へ移動" })).toContainText("topic:a → topic:a, topic:b");
    await expect(panel(page).getByRole("button", { name: "用語集: 旧名 を元に戻す" })).toBeVisible();
    await expect(panel(page).getByRole("button", { name: "差分確認" })).toBeEnabled();
    await expect(panel(page).getByRole("button", { name: "コミット" })).toBeEnabled();
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("BodyEdits", () => {
  // 文書の本文の変更は `{項目の名前}（{文書のパス}）` で並べ、ファイル全体の変更は差分確認で出す旨にする（正常系）
  test("body_edits", async ({ page }) => {
    // 準備・実行
    await openStory(page, "layout-pendingpanel--body-edits");
    // 検証
    const summary = panel(page).getByRole("button", { name: "概要（notes/n1.yaml） の行へ移動" });
    await expect(summary).toContainText("概要 → 修正後の概要");
    const file = panel(page).getByRole("button", { name: "ファイル全体（notes/n2.yaml） の行へ移動" });
    await expect(file).toContainText("差分確認で表示します");
    await expect(panel(page).getByRole("button", { name: "タグ: n1 の行へ移動" })).toBeVisible();
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("DryRunDiff", () => {
  // 差分確認を押した後、変更ごとに差分を出し、削除の行と追加の行を分ける（正常系）
  test("dry_run_diff", async ({ page }) => {
    // 準備・実行（ストーリーの play が差分確認を押す）
    await openStory(page, "layout-pendingpanel--dry-run-diff");
    // 検証
    const items = panel(page).getByRole("listitem");
    await expect(items.filter({ hasText: "概要（notes/n1.yaml）" })).toContainText("+summary: 修正後の概要");
    await expect(items.filter({ hasText: "タグ: n1" })).toContainText("+    - name: topic:b");
    expect(await axeViolations(page)).toEqual([]);
  });
});

test.describe("BodyEditInvalid", () => {
  // 差分確認で本文の変更が検査に合格しないと、その変更の行に違反した項目のパスと理由を出す（異常系）
  test("body_edit_invalid", async ({ page }) => {
    // 準備・実行（ストーリーの play が差分確認を押す）
    await openStory(page, "layout-pendingpanel--body-edit-invalid");
    // 検証
    await expect(panel(page).getByRole("alert")).toContainText("変更ごとの理由を確認してください");
    const item = panel(page).getByRole("listitem").filter({ hasText: "概要（notes/n1.yaml）" });
    await expect(item).toContainText("summary: 1 文字以上の文字列にしてください");
    await expect(panel(page).getByRole("button", { name: "再試行" })).toBeVisible();
  });
});

test.describe("Conflict", () => {
  // コミットで衝突すると、修正を残したブランチ・PR の URL・衝突した理由を出す（正常系）
  test("conflict", async ({ page }) => {
    // 準備・実行（ストーリーの play がコミットの確認を経てコミットする）
    await openStory(page, "layout-pendingpanel--conflict");
    // 検証
    const status = panel(page).getByRole("status");
    await expect(status).toContainText("ほかの変更と衝突したため、修正をブランチに残しました");
    await expect(status).toContainText("project-index/conflict/20261127-101500-00b7c00");
    await expect(status.getByRole("link", { name: "PR を開く" })).toHaveAttribute(
      "href",
      "https://github.com/o/r/pull/9",
    );
    await expect(status).toContainText("summary はほかの変更で変わっています");
  });
});

test.describe("Empty", () => {
  // 編集中の変更が 0 件のときは、その旨だけを出し、差分確認とコミットのボタンを出さない（正常系）
  test("empty", async ({ page }) => {
    // 準備・実行
    await openStory(page, "layout-pendingpanel--empty");
    // 検証
    await expect(panel(page)).toContainText("編集中の変更はありません。");
    await expect(panel(page).getByRole("button", { name: "差分確認" })).toHaveCount(0);
    await expect(panel(page).getByRole("button", { name: "コミット" })).toHaveCount(0);
  });
});

test.describe("LongLabels", () => {
  // 長い項目の名前と文書のパスを折り返し、パネルの幅を超えない（正常系）
  test("long_labels", async ({ page }) => {
    // 準備・実行
    await openStory(page, "layout-pendingpanel--long-labels");
    // 検証
    const item = panel(page).getByRole("listitem").first();
    await expect(item).toContainText("IF-155-10.yaml");
    const panelBox = await boxOf(panel(page));
    const itemBox = await boxOf(item);
    expect(itemBox.x + itemBox.width).toBeLessThanOrEqual(panelBox.x + panelBox.width + 1);
    expect(
      await item.evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
    ).toBe(true);
  });
});

test.describe("Narrow", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // 幅 48rem 未満では画面の下から出し、横にスクロールさせない（正常系）
  test("narrow", async ({ page }) => {
    // 準備・実行
    await openStory(page, "layout-pendingpanel--narrow");
    // 検証
    const box = await boxOf(panel(page));
    const viewport = viewportOf(page);
    expect(box.width).toBeGreaterThanOrEqual(viewport.width - 1);
    expect(Math.round(box.y + box.height)).toBeGreaterThanOrEqual(viewport.height - 1);
    expect(await noHorizontalScroll(page)).toBe(true);
  });
});
