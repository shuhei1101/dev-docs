import { type Page, expect, test } from "@playwright/test";

import { mockApi, problem } from "./support/api-mock";
import {
  documentResponse,
  searchResult,
  settingsSource,
  settingsView,
} from "./support/fixtures";

const missingDoc = () =>
  problem(404, { missing: "doc", value: "docs/no-such" });
const missingRef = () => problem(404, { missing: "ref", value: "no-such" });
const notServed = () =>
  problem(404, {
    missing: "not_served",
    value: "broken",
    errors: [{ path: "documents[0].paths", reason: "必須のキーがありません" }],
  });
const missingSource = () =>
  problem(404, { missing: "source", value: "unknown" });

const BROKEN_VIEW = settingsView([
  settingsSource("sample"),
  settingsSource("broken", {
    status: "not_served",
    config: ["/home/me/broken/dev-docs.yaml"],
  }),
]);

const open = async (page: Page, url: string, reply: () => ReturnType<typeof problem>, settings = settingsView()) => {
  const api = await mockApi(page, {
    document: reply,
    settings: () => ({ body: settings }),
  });
  await page.goto(url);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  return api;
};

test.describe("ページのタイトル", () => {
  // 見つからない画面のタイトルを `見つかりません | dev-docs` にする（正常系）
  test("page_title", async ({ page }) => {
    // 準備・実行
    await open(page, "/sample/docs/no-such", missingDoc);
    // 検証
    await expect(page).toHaveTitle("見つかりません | dev-docs");
  });
});

test.describe("本文へスキップ", () => {
  // キーボードでフォーカスしたときに見え、クリックで本文へフォーカスを移す（正常系）
  test("skip_link", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such", missingDoc);
    const link = page.getByRole("link", { name: "本文へスキップ" });
    // 実行
    await page.keyboard.press("Tab");
    // 検証
    await expect(link).toBeFocused();
    await expect(link).toBeVisible();
    await link.click();
    await expect(page.locator("main#main")).toBeFocused();
  });
});

test.describe("トップバー", () => {
  // 配信元のメニューで選んだ配信元のトップを開く（正常系）
  test("topbar_source_select", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such", missingDoc);
    // 実行
    await page.getByRole("button", { name: /配信元を切り替える/ }).click();
    await page.getByRole("menuitem", { name: /knowledge/ }).click();
    // 検証
    await expect(page).toHaveURL(/\/knowledge$/);
  });

  // リビジョンのメニューで選んだリビジョンの配信元のトップを開く（正常系）
  test("topbar_ref_select", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such", missingDoc);
    // 実行
    await page.getByRole("button", { name: /リビジョンを切り替える/ }).click();
    await page.getByRole("menuitem", { name: /v0\.1\.0/ }).click();
    // 検証
    await expect(page).toHaveURL(/\/sample\?rev=v0\.1\.0$/);
  });

  // 検索のボタンで検索のダイアログを開く（正常系）
  test("topbar_search_open", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such", missingDoc);
    // 実行
    await page.getByRole("button", { name: /^検索/ }).click();
    // 検証
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toBeVisible();
  });

  // 明暗のボタンで明暗を切り替え、ブラウザに保存する（正常系）
  test("topbar_color_scheme_toggle", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such", missingDoc);
    const toggle = page.getByRole("button", { name: "明暗を固定する" });
    // 実行
    await toggle.click();
    // 検証
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    const stored = await page.evaluate(() =>
      localStorage.getItem("dev-docs:preferences"),
    );
    expect(stored).toContain('"colorScheme":"dark"');
  });

  // コメントのボタンを出さない（正常系）
  test("topbar_without_comment", async ({ page }) => {
    // 準備・実行
    await open(page, "/sample/docs/no-such", missingDoc);
    // 検証
    await expect(page.getByRole("button", { name: /^コメント/ })).toHaveCount(0);
  });
});

test.describe("見出し", () => {
  // 無い文書は `文書が見つかりません` を出す（正常系）
  test("heading_when_doc_missing", async ({ page }) => {
    await open(page, "/sample/docs/no-such", missingDoc);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("文書が見つかりません");
  });

  // 無いリビジョンは `リビジョンが見つかりません` を出す（正常系）
  test("heading_when_ref_missing", async ({ page }) => {
    await open(page, "/sample?rev=no-such", missingRef);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("リビジョンが見つかりません");
  });

  // 配信していない配信元は `配信元 {ID} を配信していません` を出す（正常系）
  test("heading_when_source_not_served", async ({ page }) => {
    await open(page, "/broken/docs/a", notServed, BROKEN_VIEW);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("配信元 broken を配信していません");
  });

  // 無い配信元は `配信元 {ID} はありません` を出す（正常系）
  test("heading_when_source_unknown", async ({ page }) => {
    await open(page, "/unknown/docs/a", missingSource);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("配信元 unknown はありません");
  });
});

test.describe("説明", () => {
  // 無い文書は配信元とリビジョンを添えて理由を出す（正常系）
  test("description_when_doc_missing", async ({ page }) => {
    await open(page, "/sample/docs/no-such", missingDoc);
    await expect(page.getByText("配信元 sample のリビジョン develop に、この文書はありません。")).toBeVisible();
  });

  // Git 管理外の配信元の無い文書はリビジョンを省いた理由を出す（正常系）
  test("description_when_doc_missing_in_non_git_source", async ({ page }) => {
    // 準備
    await mockApi(page, {
      document: missingDoc,
      refs: () => ({ body: { git: false, defaultRef: "", branches: [], tags: [], commits: [] } }),
    });
    // 実行
    await page.goto("/notes/docs/no-such");
    // 検証
    await expect(page.getByText("配信元 notes に、この文書はありません。")).toBeVisible();
  });

  // 無いリビジョンは配信元とリビジョンを添えて理由を出す（正常系）
  test("description_when_ref_missing", async ({ page }) => {
    await open(page, "/sample?rev=no-such", missingRef);
    await expect(page.getByText("配信元 sample に、リビジョン no-such はありません。")).toBeVisible();
  });

  // 配信していない配信元は起動時の検証で外した理由を出す（正常系）
  test("description_when_source_not_served", async ({ page }) => {
    await open(page, "/broken/docs/a", notServed, BROKEN_VIEW);
    await expect(page.getByText("起動時の検証で、配信から外しました。")).toBeVisible();
  });

  // 無い配信元は端末の設定に無いことを出す（正常系）
  test("description_when_source_unknown", async ({ page }) => {
    await open(page, "/unknown/docs/a", missingSource);
    await expect(page.getByText("端末の設定に、この ID の配信元はありません。")).toBeVisible();
  });
});

test.describe("見つからなかったものの詳細", () => {
  // 無い文書は開こうとしたパスを等幅で出す（正常系）
  test("details_when_doc_missing", async ({ page }) => {
    await open(page, "/sample/docs/no-such", missingDoc);
    await expect(page.getByText("開こうとしたパス")).toBeVisible();
    await expect(page.locator("dd", { hasText: "docs/no-such" })).toHaveClass(/font-mono/);
  });

  // 無いリビジョンは開こうとしたリビジョンと既定のリビジョンを出す（正常系）
  test("details_when_ref_missing", async ({ page }) => {
    await open(page, "/sample?rev=no-such", missingRef);
    await expect(page.locator("dt", { hasText: "開こうとしたリビジョン" })).toBeVisible();
    await expect(page.locator("dd", { hasText: "no-such" })).toBeVisible();
    await expect(page.locator("dt", { hasText: "既定のリビジョン" })).toBeVisible();
    await expect(page.locator("dd", { hasText: "develop" })).toBeVisible();
  });

  // 配信していない配信元は外した理由と設定ファイルを出す（正常系）
  test("details_when_source_not_served", async ({ page }) => {
    await open(page, "/broken/docs/a", notServed, BROKEN_VIEW);
    await expect(page.locator("dt", { hasText: "外した理由" })).toBeVisible();
    await expect(page.locator("dd", { hasText: "documents[0].paths 必須のキーがありません" })).toBeVisible();
    await expect(page.locator("dt", { hasText: "設定ファイル" })).toBeVisible();
    await expect(page.locator("dd", { hasText: "/home/me/broken/dev-docs.yaml" })).toBeVisible();
  });

  // 無い配信元は詳細を出さない（正常系）
  test("details_when_source_unknown", async ({ page }) => {
    await open(page, "/unknown/docs/a", missingSource);
    await expect(page.locator("dl")).toHaveCount(0);
  });
});

test.describe("配信元のトップを開く", () => {
  // 無い文書は rev を保った配信元のトップを開く（正常系）
  test("top_link_when_doc_missing", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such?rev=v0.1.0", missingDoc);
    const link = page.getByRole("link", { name: "sample のトップを開く" });
    // 実行
    await expect(link).toHaveAttribute("href", "/sample?rev=v0.1.0");
    await link.click();
    // 検証
    await expect(page).toHaveURL(/\/sample\?rev=v0\.1\.0$/);
  });

  // 無いリビジョンは rev を外した配信元のトップを開く（正常系）
  test("top_link_when_ref_missing", async ({ page }) => {
    await open(page, "/sample?rev=no-such", missingRef);
    await expect(page.getByRole("link", { name: "sample のトップを開く" })).toHaveAttribute("href", "/sample");
  });

  // 配信していない配信元・無い配信元では出さない（正常系）
  test("top_link_when_source_unavailable", async ({ page }) => {
    await open(page, "/unknown/docs/a", missingSource);
    await expect(page.getByRole("link", { name: /のトップを開く/ })).toHaveCount(0);
  });
});

test.describe("設定を開く", () => {
  // 無い文書では通常の色、配信していない配信元ではプライマリの色で出す（正常系）
  test("settings_link_variant", async ({ page }) => {
    // 準備・実行
    await open(page, "/sample/docs/no-such", missingDoc);
    const outline = await page.getByRole("link", { name: "設定を開く" }).getAttribute("class");
    await open(page, "/broken/docs/a", notServed, BROKEN_VIEW);
    const primary = await page.getByRole("link", { name: "設定を開く" }).getAttribute("class");
    // 検証
    expect(outline).toContain("border-border");
    expect(primary).toContain("bg-primary");
  });

  // クリックで設定画面を開く（正常系）
  test("settings_link_click", async ({ page }) => {
    await open(page, "/sample/docs/no-such", missingDoc);
    await page.getByRole("link", { name: "設定を開く" }).click();
    await expect(page).toHaveURL(/\/_settings$/);
  });
});

test.describe("配信中の配信元", () => {
  // 配信していない・無い配信元のとき、配信中の配信元へのリンクを出す（正常系）
  test("serving_sources_when_unavailable", async ({ page }) => {
    // 準備
    await open(page, "/broken/docs/a", notServed, BROKEN_VIEW);
    const list = page.getByRole("list", { name: "配信中の配信元" });
    // 実行
    await list.getByRole("link", { name: "sample" }).click();
    // 検証
    await expect(page).toHaveURL(/\/sample$/);
  });

  // 配信中の配信元が無いときは出さない（正常系）
  test("serving_sources_when_none_serving", async ({ page }) => {
    await open(page, "/unknown/docs/a", missingSource, settingsView([]));
    await expect(page.getByRole("list", { name: "配信中の配信元" })).toHaveCount(0);
  });
});

test.describe("検索のダイアログ", () => {
  // 配信中の配信元で検索を開き、結果の選択でその文書を開く（正常系）
  test("search_dialog_result_select", async ({ page }) => {
    // 準備
    const api = await mockApi(page, {
      document: (request) =>
        request.path === "docs/doc-2"
          ? { body: documentResponse({ path: "docs/doc-2" }) }
          : missingDoc(),
      search: () => ({ body: searchResult() }),
    });
    await page.goto("/sample/docs/no-such");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // 実行
    await page.keyboard.press("Control+k");
    await page.getByPlaceholder("文書を検索").fill("ページング");
    await page.getByRole("option", { name: /文書 2/ }).click();
    // 検証
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2/);
    expect(api.callsOf("search")[0]?.request.query.get("q")).toBe("ページング");
  });

  // 配信していない配信元では検索を開かない（正常系）
  test("search_dialog_when_source_not_served", async ({ page }) => {
    await open(page, "/broken/docs/a", notServed, BROKEN_VIEW);
    await page.keyboard.press("/");
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toHaveCount(0);
  });
});

test.describe("ショートカットの一覧", () => {
  // `?` を押すと見つからない画面のキーを出す（正常系）
  test("shortcut_dialog", async ({ page }) => {
    // 準備
    await open(page, "/sample/docs/no-such", missingDoc);
    // 実行
    await page.keyboard.press("Shift+/");
    // 検証
    await expect(page.getByRole("dialog", { name: "キーボードのショートカット" })).toBeVisible();
  });
});
