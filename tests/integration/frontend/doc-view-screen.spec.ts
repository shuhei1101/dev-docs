import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

import { mockApi, problem } from "./support/api-mock";
import { boxOf, viewportOf } from "./support/geometry";
import type { Handler, Operation } from "./support/api-mock";
import {
  TABLE_KEY,
  TWO_COMMENTS,
  documentResponse,
  seededComments,
  settingsSource,
  settingsView,
} from "./support/fixtures";
import type { SeedComment } from "./support/fixtures";
import type { AliasItem } from "@/shared/api/generated/model";

type Overrides = Partial<Record<Operation, Handler>>;

const TABS_WITH_DOCS = [
  {
    title: "規約",
    active: true,
    items: [
      {
        kind: "group" as const,
        title: "設計",
        path: null,
        change: null,
        items: [
          { kind: "page" as const, title: "文書 1", path: "docs/doc-1", items: [], change: null },
          { kind: "page" as const, title: "文書 2", path: "docs/doc-2", items: [], change: null },
        ],
      },
    ],
  },
  {
    title: "補足",
    active: false,
    items: [{ kind: "page" as const, title: "補足 1", path: "notes/n-1", items: [], change: null }],
  },
  { title: "空", active: false, items: [] },
];

const DOC_1_PAGE = { kind: "page" as const, title: "文書 1", path: "docs/doc-1", items: [], change: null };
const TABS_SHARING_DOC = [
  { title: "mcp", active: true, items: [DOC_1_PAGE] },
  {
    title: "すべて",
    active: false,
    items: [
      DOC_1_PAGE,
      { kind: "page" as const, title: "文書 2", path: "docs/doc-2", items: [], change: null },
    ],
  },
];

const openDoc = async (
  page: Page,
  url = "/sample/docs/doc-1",
  overrides: Overrides = {},
) => {
  const api = await mockApi(page, overrides);
  await page.goto(url);
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  return api;
};

const openRendered = async (
  page: Page,
  url = "/sample/docs/doc-1",
  overrides: Overrides = {},
) => {
  const api = await openDoc(page, url, overrides);
  await expect(page.getByRole("heading", { level: 2, name: "概要" })).toBeVisible();
  return api;
};

const seed = async (page: Page, rows: SeedComment[]) => {
  await page.addInitScript((value) => {
    sessionStorage.setItem("dev-docs:comments", value);
  }, seededComments(rows));
};

const addComment = async (page: Page, text: string, body: string) => {
  // mdmark がコメントの部品を付け、選択の変化を受け始めるまで待つ
  await expect(page.locator("#mdmark-comment-hint")).toBeAttached();
  await page.getByText(text).selectText();
  await page.getByRole("button", { name: "コメント", exact: true }).click();
  await page.getByRole("dialog", { name: "コメントを書く" }).getByRole("textbox").fill(body);
  await page.getByRole("button", { name: "コメントを保存" }).click();
};

const panel = (page: Page) => page.getByRole("dialog", { name: /^コメント/ });

const withDiff: Handler = ({ path, query }) => {
  const base = query.get("diff");
  if (base === null && query.get("ref") === "7c0aa11") {
    return {
      body: documentResponse({
        path,
        ref: "7c0aa11",
        markdown: "# 文書 1\n\n## 概要\n\n変更前の本文\n\n## 関連\n\n同じ本文\n",
      }),
    };
  }
  return {
    body: documentResponse({
      path,
      markdown: "# 文書 1\n\n## 概要\n\n変更後の本文\n\n## 関連\n\n同じ本文\n",
      diff: base === null ? null : { base, change: "modified", changedItems: ["概要"] },
      tabs: [
        {
          title: "規約",
          active: true,
          items: [
            {
              kind: "group",
              title: "設計",
              path: null,
              change: null,
              items: [
                { kind: "page", title: "文書 1", path: "docs/doc-1", items: [], change: base === null ? null : "modified" },
                { kind: "page", title: "文書 3", path: "docs/doc-3", items: [], change: base === null ? null : "deleted" },
                { kind: "page", title: "文書 4", path: "docs/doc-4", items: [], change: base === null ? null : "added" },
              ],
            },
          ],
        },
      ],
    }),
  };
};

test.describe("ページのタイトル", () => {
  // 文書のタイトルを `{文書の名前} | {配信元の ID} | dev-docs` にする（正常系）
  test("page_title", async ({ page }) => {
    await openDoc(page);
    await expect(page).toHaveTitle("文書 1 | sample | dev-docs");
  });

  // 文書の無いタブを選んだときは `{タブ名} | {配信元の ID} | dev-docs` にする（正常系）
  test("page_title_when_empty_tab", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, tabs: TABS_WITH_DOCS }) }),
    });
    await page.getByRole("button", { name: "空" }).click();
    await expect(page).toHaveTitle("空 | sample | dev-docs");
  });
});

test.describe("本文へスキップ", () => {
  // キーボードでフォーカスしたときに見え、クリックで本文の領域へフォーカスを移す（正常系）
  test("skip_link", async ({ page }) => {
    // 準備
    await openDoc(page);
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
  // `sourceSelect` で選んだ配信元のトップを開く（正常系）
  test("topbar_source_select", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: /配信元を切り替える/ }).click();
    await page.getByRole("menuitem", { name: /knowledge/ }).click();
    await expect(page).toHaveURL(/\/knowledge$/);
  });

  // `refSelect` で rev を書き換えて同じ文書を開き直す（正常系）
  test("topbar_ref_select", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: /リビジョンを切り替える/ }).click();
    await page.getByRole("menuitem", { name: /v0\.1\.0/ }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1\?rev=v0\.1\.0$/);
  });

  // 開いているのが既定のリビジョンのとき、`compareStart` で最近の commit の 2 件目を base に入れる（正常系）
  test("topbar_compare_start_when_default_ref", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: /リビジョンを切り替える/ }).click();
    await page.getByRole("menuitem", { name: "別のリビジョンと比較" }).click();
    await expect(page).toHaveURL(/base=7c0aa11/);
  });

  // 開いているのが既定以外のリビジョンのとき、`compareStart` で既定のリビジョンを base に入れる（正常系）
  test("topbar_compare_start_when_other_ref", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?rev=feat%2Ffrontend%2Freact-spa");
    await page.getByRole("button", { name: /リビジョンを切り替える/ }).click();
    await page.getByRole("menuitem", { name: "別のリビジョンと比較" }).click();
    await expect(page).toHaveURL(/base=develop/);
  });

  // `searchOpen` で検索のダイアログを開く（正常系）
  test("topbar_search_open", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: /^検索/ }).click();
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toBeVisible();
  });

  // `commentPanelToggle` でコメントのパネルを開閉する（正常系）
  test("topbar_comment_panel_toggle", async ({ page }) => {
    await openDoc(page);
    const toggle = page.getByRole("button", { name: /^コメント \d+ 件$/ });
    await toggle.click();
    await expect(panel(page)).toBeVisible();
    await toggle.click();
    await expect(panel(page)).toHaveCount(0);
  });

  // 狭い幅で `sidebarOpen` が文書の一覧のドロワーを開く（正常系）
  test("topbar_sidebar_open", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDoc(page);
    await page.getByRole("button", { name: "文書の一覧を開く" }).click();
    await expect(page.getByRole("dialog", { name: "文書の一覧" })).toBeVisible();
  });

  // `colorSchemeToggle` で明暗を切り替え、ブラウザに保存する（正常系）
  test("topbar_color_scheme_toggle", async ({ page }) => {
    await openDoc(page);
    const toggle = page.getByRole("button", { name: "明暗を固定する" });
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    const stored = await page.evaluate(() => localStorage.getItem("dev-docs:preferences"));
    expect(stored).toContain('"colorScheme":"dark"');
  });

  // 配信中の配信元だけをメニューに並べ、書き込み権限を添える（正常系）
  test("topbar_sources_from_settings", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", {
      settings: () => ({
        body: settingsView([
          settingsSource("sample"),
          settingsSource("knowledge", { scope: { read: ["/a/**"], write: ["/b/**"] } }),
          settingsSource("broken", { status: "not_served" }),
        ]),
      }),
    });
    await page.getByRole("button", { name: /配信元を切り替える/ }).click();
    await expect(page.getByRole("menuitem")).toHaveCount(2);
    await expect(page.getByRole("menuitem", { name: /sample/ })).toContainText("読み書き");
  });
});

test.describe("種類のタブ", () => {
  const withTabs: Overrides = {
    document: ({ path }) => ({ body: documentResponse({ path, tabs: TABS_WITH_DOCS }) }),
  };

  // 配信元の `nav` の並び順にタブを出し、開いている文書のタブを現在地にする（正常系）
  test("tabs_order_and_current", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", withTabs);
    const tabs = page.getByRole("navigation", { name: "文書の種類" });
    await expect(tabs.locator("a, button")).toHaveText(["規約", "補足", "空"]);
    await expect(tabs.getByRole("link", { name: "規約" })).toHaveAttribute("aria-current", "page");
  });

  // クリックでそのタブのサイドバーの一番上の文書を開く（正常系）
  test("tabs_click", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", withTabs);
    await page.getByRole("link", { name: "補足", exact: true }).click();
    await expect(page).toHaveURL(/\/sample\/notes\/n-1/);
  });

  // 1 つの文書が 2 つのタブに当たるとき、後のタブを押すとそのタブを現在地にしてサイドバーを替える（正常系）
  test("tabs_click_when_doc_in_two_tabs", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, tabs: TABS_SHARING_DOC }) }),
    });
    const tabs = page.getByRole("navigation", { name: "文書の種類" });
    await tabs.getByRole("link", { name: "すべて" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1\?tab=1$/);
    await expect(tabs.getByRole("link", { name: "すべて" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("navigation", { name: "文書の一覧" }).getByRole("link")).toHaveText([
      "文書 1",
      "文書 2",
    ]);
  });

  // 文書の無いタブは URL を変えず、文書が無いことの表示を出す（正常系）
  test("tabs_click_when_empty", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", withTabs);
    await page.getByRole("button", { name: "空" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1$/);
    await expect(page.getByRole("heading", { level: 2, name: "空の文書はありません" })).toBeVisible();
  });
});

test.describe("文書の一覧", () => {
  // group を見出し、page を文書の名前のリンクにして並べ、開いている文書を現在地にする（正常系）
  test("sidebar_groups_and_pages", async ({ page }) => {
    await openDoc(page);
    const list = page.getByRole("navigation", { name: "文書の一覧" });
    await expect(list.getByText("設計", { exact: true })).toBeVisible();
    await expect(list.getByRole("link")).toHaveText(["文書 1", "文書 2"]);
    await expect(list.getByRole("link", { name: "文書 1" })).toHaveAttribute("aria-current", "page");
  });

  // page のクリックで rev と base を保った文書を開く（正常系）
  test("sidebar_click_keeps_rev_and_base", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?rev=develop&base=7c0aa11");
    await page.getByRole("navigation", { name: "文書の一覧" }).getByRole("link", { name: "文書 2" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2\?rev=develop&base=7c0aa11$/);
  });

  // 削除された page は rev を base にして base を外した文書を開く（正常系）
  test("sidebar_click_when_deleted", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?rev=develop&base=7c0aa11", { document: withDiff });
    await page.getByRole("navigation", { name: "文書の一覧" }).getByRole("link", { name: /文書 3/ }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-3\?rev=7c0aa11$/);
  });

  // 画面幅が 48rem 未満のときは出さない（正常系）
  test("sidebar_hidden_when_narrow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDoc(page);
    await expect(page.getByRole("navigation", { name: "文書の一覧" })).toBeHidden();
  });
});

test.describe("文書の変化のマーカー", () => {
  // base があるとき、追加・変更・削除をアイコンで出し、削除の page に取り消し線を引く（正常系）
  test("change_markers", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    const list = page.getByRole("navigation", { name: "文書の一覧" });
    await expect(list.getByRole("img", { name: "変更" })).toHaveCount(1);
    await expect(list.getByRole("img", { name: "追加" })).toHaveCount(1);
    await expect(list.getByRole("img", { name: "削除" })).toHaveCount(1);
    await expect(list.getByText("文書 3")).toHaveClass(/line-through/);
  });

  // base が無いときは出さない（正常系）
  test("change_markers_without_base", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withDiff });
    await expect(page.getByRole("navigation", { name: "文書の一覧" }).getByRole("img")).toHaveCount(0);
  });
});

test.describe("文書の一覧のドロワー", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  // 文書を開くと閉じる（正常系）
  test("drawer_closes_on_navigate", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: "文書の一覧を開く" }).click();
    await page.getByRole("dialog", { name: "文書の一覧" }).getByRole("link", { name: "文書 2" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2/);
    await expect(page.getByRole("dialog", { name: "文書の一覧" })).toHaveCount(0);
  });

  // Esc で閉じ、開いたボタンへフォーカスを戻す（正常系）
  test("drawer_closes_on_escape", async ({ page }) => {
    await openDoc(page);
    const opener = page.getByRole("button", { name: "文書の一覧を開く" });
    await opener.click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "文書の一覧" })).toHaveCount(0);
    await expect(opener).toBeFocused();
  });
});

test.describe("パンくず", () => {
  // `{配信元の ID}` / `{タブ名}` / `{group}` / `{文書の名前}` を出し、配信元とタブだけをリンクにする（正常系）
  test("breadcrumb", async ({ page }) => {
    await openDoc(page);
    const crumb = page.getByRole("navigation", { name: "パンくず" });
    await expect(crumb.getByRole("listitem")).toHaveText(["sample", "規約", "設計", "文書 1"]);
    await expect(crumb.getByRole("link")).toHaveText(["sample", "規約"]);
    await expect(crumb.getByText("文書 1")).toHaveAttribute("aria-current", "page");
  });

  // 配信元の ID のクリックで配信元のトップを開く（正常系）
  test("breadcrumb_source_link", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-2");
    await page.getByRole("navigation", { name: "パンくず" }).getByRole("link", { name: "sample" }).click();
    await expect(page).toHaveURL(/\/sample$/);
  });

  // タブ名のクリックでそのタブの一番上の文書を開く（正常系）
  test("breadcrumb_tab_link", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-2");
    await page.getByRole("navigation", { name: "パンくず" }).getByRole("link", { name: "規約" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1/);
  });
});

test.describe("文書のタイトル", () => {
  // 文書の名前を見出し 1 に出す（正常系）
  test("doc_title", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-2");
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("文書 2");
  });
});

test.describe("文書の情報", () => {
  // 種類のバッジ・文書のパス(等幅)・`更新 MM/DD HH:mm JST` を出し、time に ISO 8601 を持つ（正常系）
  test("doc_info", async ({ page }) => {
    await openDoc(page);
    const main = page.getByRole("main");
    await expect(main.locator("header").getByText("規約", { exact: true })).toBeVisible();
    await expect(main.locator("header code")).toHaveText("docs/doc-1");
    await expect(main.locator("header code")).toHaveClass(/font-mono/);
    const time = main.locator("time");
    await expect(time).toHaveText("更新 10/26 14:40 JST");
    await expect(time).toHaveAttribute("datetime", "2026-10-26T05:40:00Z");
  });
});

test.describe("読み込み中の表示", () => {
  // 取得が 1 秒を超えたときだけ、タイトル・情報・本文の形の枠を出す（正常系）
  test("loading_skeleton", async ({ page }) => {
    // 準備
    await mockApi(page, {
      document: ({ path }) => ({ body: documentResponse({ path }), delayMs: 2500 }),
    });
    // 実行
    await page.goto("/sample/docs/doc-1");
    // 検証
    const skeleton = page.getByLabel("文書を読み込んでいます");
    await expect(skeleton).toHaveCount(0);
    await expect(skeleton).toBeVisible({ timeout: 2000 });
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  });

  // 前の文書があれば、取得の間も前の文書を出したままにする（正常系）
  test("loading_keeps_previous_doc", async ({ page }) => {
    // 準備
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path }),
        delayMs: path === "docs/doc-2" ? 2000 : 0,
      }),
    });
    // 実行
    await page.getByRole("navigation", { name: "文書の一覧" }).getByRole("link", { name: "文書 2" }).click();
    // 検証
    await page.waitForTimeout(1500);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("文書 1");
    await expect(page.getByLabel("文書を読み込んでいます")).toHaveCount(0);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("文書 2");
  });
});

test.describe("差分の案内", () => {
  // base があり Git の配信元のとき、比較元と比較先の選択と解除のボタンを出す（正常系）
  test("diff_banner_visible", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    const banner = page.getByRole("region", { name: "差分" });
    await expect(banner.getByRole("combobox", { name: "比較元" })).toContainText("7c0aa11");
    await expect(banner.getByRole("combobox", { name: "比較先" })).toContainText("develop");
    await expect(banner.getByRole("button", { name: "差分の強調を解除" })).toBeVisible();
  });

  // base が無いときは出さない（正常系）
  test("diff_banner_hidden_without_base", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withDiff });
    await expect(page.getByRole("region", { name: "差分" })).toHaveCount(0);
  });

  // Git 管理外の配信元では出さない（正常系）
  test("diff_banner_hidden_when_non_git", async ({ page }) => {
    await openDoc(page, "/notes/docs/doc-1?base=7c0aa11", {
      document: ({ source, path }) => ({
        body: documentResponse({ source, path, ref: null, diff: null }),
      }),
      refs: () => ({ body: { git: false, defaultRef: "", branches: [], tags: [], commits: [] } }),
    });
    await expect(page.getByRole("region", { name: "差分" })).toHaveCount(0);
  });
});

test.describe("比較元の選択", () => {
  // 選択肢はリビジョンのメニューと同じ並びで、一覧に無い base は先頭に足す。選び直すと base を書き換える（正常系）
  test("base_select", async ({ page }) => {
    // 準備
    await openDoc(page, "/sample/docs/doc-1?base=zzz9999", { document: withDiff });
    const select = page.getByRole("combobox", { name: "比較元" });
    // 実行
    await select.click();
    // 検証
    await expect(page.getByRole("option")).toHaveText([
      "zzz9999",
      "develop",
      "feat/frontend/react-spa",
      "v0.1.0",
      "8b1d4e0",
      "7c0aa11",
    ]);
    await page.getByRole("option", { name: "v0.1.0" }).click();
    await expect(page).toHaveURL(/base=v0\.1\.0/);
  });
});

test.describe("比較先の選択", () => {
  // 開いているリビジョンを初期値にし、選び直すと rev を書き換える（正常系）
  test("head_select", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    const select = page.getByRole("combobox", { name: "比較先" });
    await expect(select).toContainText("develop");
    await select.click();
    await page.getByRole("option", { name: "v0.1.0" }).click();
    await expect(page).toHaveURL(/rev=v0\.1\.0/);
  });
});

test.describe("差分の強調を解除", () => {
  // クリックで base を外した同じ文書を開き、マーカーを消す（正常系）
  test("diff_clear", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    await page.getByRole("button", { name: "差分の強調を解除" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1$/);
    await expect(page.getByRole("region", { name: "差分" })).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "文書の一覧" }).getByRole("img")).toHaveCount(0);
  });
});

test.describe("変換の失敗", () => {
  const failed = (error: Record<string, unknown>): Overrides => ({
    document: ({ path }) => ({
      body: documentResponse({ path, markdown: null, tableKeys: [], conversionError: error as never }),
    }),
  });

  // 制限時間の超過のとき、見出し・説明・種類/スクリプト/原因の一覧を出し、本文を描かない（正常系）
  test("conversion_error_when_timeout", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", failed({
      reason: "timeout",
      kind: "custom",
      script: "scripts/convert.py",
      detail: "1 秒を超えました",
    }));
    const alert = page.getByRole("alert");
    await expect(alert).toContainText("本文を変換できませんでした");
    await expect(alert).toContainText("配信元の変換のスクリプトが制限時間を超えたため、止めました。スクリプトを修正してから、再読み込みしてください。");
    await expect(alert.locator("dt")).toHaveText(["種類", "スクリプト", "原因"]);
    await expect(alert.locator("dd")).toHaveText(["custom", "scripts/convert.py", "1 秒を超えました"]);
    await expect(page.getByRole("heading", { level: 2, name: "概要" })).toHaveCount(0);
  });

  // YAML を読めないとき、ファイル/場所/原因の一覧を出す（正常系）
  test("conversion_error_when_invalid_yaml", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", failed({
      reason: "invalid_yaml",
      kind: "sample",
      file: "docs/doc-1.yaml",
      line: 3,
      column: 5,
      detail: "mapping values are not allowed here",
    }));
    const alert = page.getByRole("alert");
    await expect(alert.locator("dt")).toHaveText(["ファイル", "場所", "原因"]);
    await expect(alert.locator("dd").nth(1)).toHaveText("3 行 5 列");
  });
});

test.describe("再読み込み", () => {
  // クリックで同じ条件の文書の取得を呼び直す（正常系）
  test("reload_button", async ({ page }) => {
    // 準備
    const api = await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({
          path,
          markdown: null,
          conversionError: { reason: "exit", kind: "custom", script: "s.py", detail: "失敗" },
        }),
      }),
    });
    const before = api.callsOf("document").length;
    // 実行
    await page.getByRole("button", { name: "再読み込み" }).click();
    // 検証
    await expect.poll(() => api.callsOf("document").length).toBeGreaterThan(before);
  });
});

test.describe("文書が無いことの表示", () => {
  const withTabs: Overrides = {
    document: ({ path }) => ({ body: documentResponse({ path, tabs: TABS_WITH_DOCS }) }),
  };

  // 見出し `{タブ名}の文書はありません` と、リビジョンつきの説明を出す（正常系）
  test("empty_tab_message", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", withTabs);
    await page.getByRole("button", { name: "空" }).click();
    await expect(page.getByRole("heading", { level: 2, name: "空の文書はありません" })).toBeVisible();
    await expect(
      page.getByText("このタブの nav.tabs[2].paths に当たる文書が、リビジョン develop にありません。"),
    ).toBeVisible();
  });

  // Git 管理外の配信元ではリビジョンを省く（正常系）
  test("empty_tab_message_when_non_git", async ({ page }) => {
    await openDoc(page, "/notes/docs/doc-1", {
      document: ({ source, path }) => ({
        body: documentResponse({ source, path, ref: null, tabs: TABS_WITH_DOCS }),
      }),
    });
    await page.getByRole("button", { name: "空" }).click();
    await expect(
      page.getByText("このタブの nav.tabs[2].paths に当たる文書が にありません。"),
    ).toBeVisible();
  });
});

test.describe("本文", () => {
  // 最初の見出し 1 を除いて描く(見出し 1 は文書のタイトルだけ)（正常系）
  test("body_without_first_h1", async ({ page }) => {
    await openRendered(page);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveCount(1);
  });

  // 同じ配信元の文書へのリンクは、画面を読み込み直さず rev を保って開く（正常系）
  test("body_internal_link", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1?rev=develop");
    await page.evaluate(() => {
      (window as unknown as { __spa: boolean }).__spa = true;
    });
    // 実行
    await page.getByRole("link", { name: "文書 2", exact: true }).last().click();
    // 検証
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2\?rev=develop$/);
    expect(await page.evaluate(() => (window as unknown as { __spa?: boolean }).__spa)).toBe(true);
  });

  // 外の URL は別のタブで開く（正常系）
  test("body_external_link", async ({ page, context }) => {
    // 準備
    await context.route("https://example.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<title>example</title>" }),
    );
    await openRendered(page);
    // 実行
    const popup = page.waitForEvent("popup");
    await page.getByRole("link", { name: "公式" }).click();
    // 検証
    expect((await popup).url()).toBe("https://example.com/");
  });

  // 本文の中の存在しない文書へのリンクは見つからない画面を出す（異常系）
  test("body_internal_link_when_missing", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) =>
        path === "docs/doc-2"
          ? problem(404, { missing: "doc", value: "docs/doc-2" })
          : { body: documentResponse({ path }) },
    });
    // 実行
    await page.getByRole("link", { name: "文書 2", exact: true }).last().click();
    // 検証
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("文書が見つかりません");
  });
});

test.describe("列の表示のメニュー", () => {
  // `+columns` の表に `列の表示` を出す（正常系）
  test("columns_menu_visible", async ({ page }) => {
    await openRendered(page);
    await expect(page.getByRole("button", { name: /^列の表示/ })).toBeVisible();
  });

  // 隠した列を表から除き、件数を `列の表示` に添える（正常系）
  test("columns_menu_hidden_columns", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, columns: { [TABLE_KEY]: ["備考"] } }),
      }),
    });
    await expect(page.locator("th:visible")).toHaveText(["キー", "名称"]);
    await expect(page.getByRole("button", { name: /1 列を隠しています/ })).toBeVisible();
  });

  // 列の出し入れのたびに、その表の隠した列を保存する（正常系）
  test("columns_menu_save", async ({ page }) => {
    // 準備
    const api = await openRendered(page);
    await page.getByRole("button", { name: /^列の表示/ }).click();
    // 実行
    await page.getByRole("dialog", { name: "表示する列" }).getByLabel("備考").uncheck();
    // 検証
    await expect.poll(() => api.callsOf("putColumns").length).toBe(1);
    expect(api.callsOf("putColumns")[0]?.request.body).toEqual({
      table: TABLE_KEY,
      hidden: ["備考"],
    });
    await expect(page.locator("th:visible")).toHaveText(["キー", "名称"]);
  });

  // 保存に失敗したら通知を出し、表は切り替えたままにする（異常系）
  test("columns_menu_save_failure", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", {
      putColumns: () => problem(500),
    });
    await page.getByRole("button", { name: /^列の表示/ }).click();
    // 実行
    await page.getByRole("dialog", { name: "表示する列" }).getByLabel("備考").uncheck();
    // 検証
    await expect(page.getByText("列の表示を保存できませんでした。")).toBeVisible();
    await expect(page.locator("th:visible")).toHaveText(["キー", "名称"]);
  });
});

test.describe("目次", () => {
  // 見出し `目次` と、本文の見出し 2・3 を階層どおりに並べる（正常系）
  test("toc_items", async ({ page }) => {
    await openRendered(page);
    const toc = page.getByRole("navigation", { name: "目次" });
    await expect(toc.getByRole("heading", { level: 2, name: "目次" })).toBeVisible();
    await expect(toc.getByRole("link")).toHaveText(["概要", "項目", "項目の表", "関連"]);
  });

  // 画面の中で別の文書へ移ると、移った先の文書の見出しで目次を描き直す（正常系）
  test("toc_after_doc_changed", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({
          path,
          markdown:
            path === "docs/doc-2"
              ? "# 文書 2\n\n## 別の概要\n\n## 別の関連\n"
              : "# 文書 1\n\n## 概要\n\n## 関連\n",
        }),
      }),
    });
    const toc = page.getByRole("navigation", { name: "目次" });
    await expect(toc.getByRole("link")).toHaveText(["概要", "関連"]);
    // 実行
    await page
      .getByRole("navigation", { name: "文書の一覧" })
      .getByRole("link", { name: "文書 2" })
      .click();
    // 検証
    await expect(page.getByRole("heading", { level: 2, name: "別の概要" })).toBeVisible();
    await expect(toc.getByRole("link")).toHaveText(["別の概要", "別の関連"]);
  });

  // 画面幅が 80rem 未満のときは出さない（正常系）
  test("toc_hidden_when_narrow", async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 });
    await openRendered(page);
    await expect(page.getByRole("navigation", { name: "目次" })).toBeHidden();
  });

  // クリックでその見出しへ移る（正常系）
  test("toc_click", async ({ page }) => {
    await openRendered(page);
    await page.getByRole("navigation", { name: "目次" }).getByRole("link", { name: "関連" }).click();
    await expect(page).toHaveURL(/#関連$|#%E9%96%A2%E9%80%A3$/);
  });

  // 画面の一番上にある見出しを現在地にし、スクロールに合わせて移す（正常系）
  test("toc_current_heading", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({
          path,
          markdown: `# 文書 1\n\n## 概要\n\n${"本文\n\n".repeat(60)}## 関連\n\n${"本文\n\n".repeat(60)}`,
        }),
      }),
    });
    const toc = page.getByRole("navigation", { name: "目次" });
    await expect(toc.getByRole("link", { name: "概要" })).toHaveAttribute("aria-current", "true");
    // 実行
    await page
      .getByRole("heading", { level: 2, name: "関連" })
      .evaluate((element) => element.scrollIntoView({ block: "start" }));
    // 検証
    await expect(toc.getByRole("link", { name: "関連" })).toHaveAttribute("aria-current", "true");
  });
});

test.describe("目次の変更のマーカー", () => {
  // base と中身が違うセクションの見出しに変更のマーカーを付ける（正常系）
  test("toc_change_marker", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    const toc = page.getByRole("navigation", { name: "目次" });
    await expect(toc.getByRole("link", { name: /概要/ })).toContainText("変更");
    await expect(toc.getByRole("link", { name: /関連/ })).not.toContainText("変更");
  });
});

test.describe("コメントの追加", () => {
  // 本文の文字列を選んで保存すると、コメントを溜め、パネルを開いて一覧とトップバーの件数を描き直す（正常系）
  test("comment_add", async ({ page }) => {
    // 準備
    await openRendered(page);
    // 実行
    await addComment(page, "文書 1 の本文です。", "ここを直したい");
    // 検証
    await expect(panel(page)).toBeVisible();
    await expect(panel(page).getByText("ここを直したい")).toBeVisible();
    await expect(page.getByRole("button", { name: "コメント 1 件" })).toBeVisible();
  });
});

test.describe("コメントのパネル", () => {
  // 見出し `コメント` と `{件数} 件` を出す（正常系）
  test("panel_heading", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await expect(panel(page)).toContainText("コメント");
    await expect(panel(page)).toContainText("2 件");
  });

  // 他の文書のコメントも並べる（正常系）
  test("panel_lists_other_docs", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await expect(panel(page).getByRole("listitem")).toHaveCount(2);
  });
});

test.describe("コメントのパネルの位置", () => {
  // 画面幅が 48rem 以上では本文の右に、トップバーを隠さずに出す（正常系）
  test("panel_position_on_the_right", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    const box = await boxOf(panel(page));
    expect(box.x + box.width).toBeGreaterThanOrEqual(1279);
    expect(box.y).toBeGreaterThanOrEqual(48);
  });

  // 画面幅が 48rem 未満では画面の下から出す（正常系）
  test("panel_position_when_narrow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    const box = await boxOf(panel(page));
    expect(box.y + box.height).toBeGreaterThanOrEqual(843);
    expect(box.width).toBeGreaterThanOrEqual(389);
    expect(box.y).toBeGreaterThan(200);
  });
});

test.describe("コメントのパネルを閉じる", () => {
  // クリックでパネルを閉じ、トップバーのコメントのボタンへフォーカスを戻す（正常系）
  test("panel_close_button", async ({ page }) => {
    await openDoc(page);
    const toggle = page.getByRole("button", { name: /^コメント \d+ 件$/ });
    await toggle.click();
    await panel(page).getByRole("button", { name: "閉じる" }).click();
    await expect(panel(page)).toHaveCount(0);
    await expect(toggle).toBeFocused();
  });

  // Esc でパネルを閉じ、トップバーのコメントのボタンへフォーカスを戻す（正常系）
  test("panel_close_by_escape", async ({ page }) => {
    await openDoc(page);
    const toggle = page.getByRole("button", { name: /^コメント \d+ 件$/ });
    await toggle.click();
    await page.keyboard.press("Escape");
    await expect(panel(page)).toHaveCount(0);
    await expect(toggle).toBeFocused();
  });
});

test.describe("すべて選択", () => {
  const openPanel = async (page: Page, rows: SeedComment[]) => {
    await seed(page, rows);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
  };

  // 全て選んでいればオン、一部なら途中の状態にする（正常系）
  test("select_all_state", async ({ page }) => {
    await openPanel(page, TWO_COMMENTS);
    const all = panel(page).getByRole("checkbox", { name: "すべて選択" });
    await expect(all).toBeChecked();
    await panel(page).getByRole("checkbox", { name: "2 件目を選択" }).uncheck();
    await expect(all).toHaveAttribute("aria-checked", "mixed");
  });

  // 切り替えで全てのコメントの選択をそろえる（正常系）
  test("select_all_toggle", async ({ page }) => {
    await openPanel(page, TWO_COMMENTS);
    const all = panel(page).getByRole("checkbox", { name: "すべて選択" });
    await all.uncheck();
    await expect(panel(page).getByRole("checkbox", { name: "1 件目を選択" })).not.toBeChecked();
    await expect(panel(page).getByRole("checkbox", { name: "2 件目を選択" })).not.toBeChecked();
    await all.check();
    await expect(panel(page).getByRole("checkbox", { name: "1 件目を選択" })).toBeChecked();
  });

  // 溜めたコメントが無いときは出さない（正常系）
  test("select_all_hidden_when_empty", async ({ page }) => {
    await openPanel(page, []);
    await expect(panel(page).getByRole("checkbox")).toHaveCount(0);
  });
});

test.describe("コメントの選択", () => {
  // 追加したときはオンで、切り替えでそのコメントの選択を変える（正常系）
  test("comment_select", async ({ page }) => {
    await openRendered(page);
    await addComment(page, "文書 1 の本文です。", "選択の確認");
    const box = panel(page).getByRole("checkbox", { name: "1 件目を選択" });
    await expect(box).toBeChecked();
    await box.uncheck();
    await expect(box).not.toBeChecked();
  });
});

test.describe("コメントの場所", () => {
  const openPanel = async (page: Page) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
  };

  // `{文書の名前} › {見出し}` を出し、見出しが無いときは `{文書の名前} › 冒頭` を出す（正常系）
  test("place_text", async ({ page }) => {
    await openPanel(page);
    await expect(panel(page).getByRole("button", { name: "文書 1 › 概要" })).toBeVisible();
    await expect(panel(page).getByRole("button", { name: "文書 2 › 冒頭" })).toBeVisible();
  });

  // 他の文書のコメントは、コメントしたリビジョンのその文書を開いてから移る（正常系）
  test("place_click_other_doc", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "文書 2 › 冒頭" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2\?rev=develop$/);
  });
});

test.describe("コメントの場所への移動", () => {
  const LONG_DOC = (title: string, last: string) =>
    `# ${title}\n\n## 概要\n\n${"本文です。\n\n".repeat(80)}## 関連\n\n${last}\n`;
  const document: Handler = ({ path }) => ({
    body: documentResponse({
      path,
      markdown: LONG_DOC(path === "docs/doc-2" ? "文書 2" : "文書 1", path === "docs/doc-2" ? "文書 2 の末尾の文" : "文書 1 の末尾の文"),
    }),
  });
  const mark = (page: Page, text: string) =>
    page.locator(".mdmark-comment-mark").filter({ hasText: text });

  // 同じ文書のコメントは、本文のその印が画面に入るまでスクロールする（正常系）
  test("place_scroll_same_doc", async ({ page }) => {
    // 準備
    await seed(page, [
      { id: "c1", path: "docs/doc-1", docTitle: "文書 1", headings: ["関連"], quote: "文書 1 の末尾の文", body: "末尾の確認" },
    ]);
    await openRendered(page, "/sample/docs/doc-1", { document });
    await expect(mark(page, "文書 1 の末尾の文")).not.toBeInViewport();
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    // 実行
    await panel(page).getByRole("button", { name: "文書 1 › 関連" }).click();
    // 検証
    await expect(mark(page, "文書 1 の末尾の文")).toBeInViewport();
  });

  // 印が見つからないまま別の文書へ移ったら、後で元の文書を開き直して同じ文字列の印が付いてもスクロールしない（正常系）
  test("place_scroll_cleared_when_doc_left", async ({ page }) => {
    // 準備（同じ文字列が 2 か所あり、前後の文字列が合わないため、場所を選んだ時点では印が付かない）
    const twice = `# 文書 2\n\n## 概要\n\n${"本文です。\n\n".repeat(40)}中ほどの文\n\n${"本文です。\n\n".repeat(40)}中ほどの文\n\n${"本文です。\n\n".repeat(40)}`;
    await seed(page, [
      { id: "c2", path: "docs/doc-2", docTitle: "文書 2", headings: ["概要"], quote: "中ほどの文", prefix: "前の文字列", suffix: "後の文字列", body: "見つからない確認" },
    ]);
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, markdown: path === "docs/doc-2" ? twice : LONG_DOC("文書 1", "文書 1 の末尾の文") }),
      }),
    });
    const sidebar = page.getByRole("navigation", { name: "文書の一覧" });
    const heading = page.getByRole("main").getByRole("heading", { level: 1 });
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("button", { name: "文書 2 › 概要" }).click();
    await expect(heading).toHaveText("文書 2");
    await expect(page.locator(".mdmark-comment-mark")).toHaveCount(0);
    // 実行（文書 1 へ移り、文書 2 を開き直して、1 つ目の「中ほどの文」を画面の上端に置いてコメントを付ける）
    await sidebar.getByRole("link", { name: "文書 1" }).click();
    await expect(heading).toHaveText("文書 1");
    await sidebar.getByRole("link", { name: "文書 2" }).click();
    await expect(heading).toHaveText("文書 2");
    const target = page.getByText("中ほどの文").first();
    await target.evaluate((element) => element.scrollIntoView({ block: "start" }));
    const before = await page.evaluate(() => window.scrollY);
    await target.selectText();
    await page.getByRole("button", { name: "コメント", exact: true }).click();
    await page.getByRole("dialog", { name: "コメントを書く" }).getByRole("textbox").fill("開き直した後の確認");
    await page.getByRole("button", { name: "コメントを保存" }).click();
    // 検証
    await expect(mark(page, "中ほどの文")).toHaveCount(1);
    await page.waitForTimeout(500);
    expect(Math.abs((await page.evaluate(() => window.scrollY)) - before)).toBeLessThan(5);
  });

  // 他の文書のコメントは、その文書を開いた後に本文の印が画面に入るまでスクロールする（正常系）
  test("place_scroll_other_doc", async ({ page }) => {
    // 準備
    await seed(page, [
      { id: "c2", path: "docs/doc-2", docTitle: "文書 2", headings: ["関連"], quote: "文書 2 の末尾の文", body: "別の文書の確認" },
    ]);
    await openRendered(page, "/sample/docs/doc-1", { document });
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    // 実行
    await panel(page).getByRole("button", { name: "文書 2 › 関連" }).click();
    // 検証
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("文書 2");
    await expect(mark(page, "文書 2 の末尾の文")).toBeInViewport();
  });
});

test.describe("コメントの引用", () => {
  // 選んだ文字列を `「…」` で出し、長いときは 2 行で切る（正常系）
  test("quote_text", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    const quote = panel(page).locator("blockquote").first();
    await expect(quote).toHaveText("「一覧のページングは先頭から数えます」");
    await expect(quote).toHaveClass(/line-clamp-2/);
  });
});

test.describe("コメントの本文", () => {
  // 書いたコメントを出す（正常系）
  test("comment_body", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await expect(panel(page).getByText("ページングの数え方を確認したい")).toBeVisible();
  });
});

test.describe("コメントの修正", () => {
  const openPanel = async (page: Page) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
  };

  // 鉛筆のボタンで本文をコメントの修正欄に替え、修正中は修正・削除のボタンを出さない（正常系）
  test("edit_button", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await expect(panel(page).getByRole("textbox", { name: "コメント" })).toHaveValue("ページングの数え方を確認したい");
    await expect(panel(page).getByRole("button", { name: "修正" })).toHaveCount(1);
  });

  // 修正欄は初期フォーカスを持つ（正常系）
  test("edit_field_focus", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await expect(panel(page).getByRole("textbox", { name: "コメント" })).toBeFocused();
  });

  // 保存で本文を書き戻す（正常系）
  test("edit_save", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await panel(page).getByRole("textbox", { name: "コメント" }).fill("直した本文");
    await panel(page).getByRole("button", { name: "保存" }).click();
    await expect(panel(page).getByText("直した本文")).toBeVisible();
    await expect(panel(page).getByRole("textbox")).toHaveCount(0);
  });

  // キャンセルで元の本文に戻す（正常系）
  test("edit_cancel", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await panel(page).getByRole("textbox", { name: "コメント" }).fill("捨てる本文");
    await panel(page).getByRole("button", { name: "キャンセル" }).click();
    await expect(panel(page).getByText("ページングの数え方を確認したい")).toBeVisible();
  });

  // Esc で元の本文に戻す（正常系）
  test("edit_cancel_by_escape", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await page.keyboard.press("Escape");
    await expect(panel(page).getByRole("textbox")).toHaveCount(0);
    await expect(panel(page)).toBeVisible();
  });

  // 空白だけの本文は保存できず、修正欄の下にエラーを出す（異常系）
  test("edit_save_when_blank", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await panel(page).getByRole("textbox", { name: "コメント" }).fill("   ");
    await panel(page).getByRole("button", { name: "保存" }).click();
    await expect(panel(page).getByText("コメントを入力してください。")).toBeVisible();
    await expect(panel(page).getByRole("textbox")).toHaveCount(1);
  });
});

test.describe("コメントの削除", () => {
  // クリックでそのコメントを削除し、一覧と件数を描き直す（正常系）
  test("delete_button", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("button", { name: "削除" }).first().click();
    await expect(panel(page).getByRole("listitem")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "コメント 1 件" })).toBeVisible();
  });
});

test.describe("選択をコピー", () => {
  const openPanel = async (page: Page) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
  };

  // `選択 {件数} 件をコピー` を出し、選んだコメントをまとめてコピーして通知を出す（正常系）
  test("copy_button", async ({ page }) => {
    // 準備
    await openPanel(page);
    // 実行
    await panel(page).getByRole("button", { name: "選択 2 件をコピー" }).click();
    // 検証
    await expect(page.getByText("選択 2 件をクリップボードにコピーしました。")).toBeVisible();
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text).toContain("### 文書 1 › 概要");
    expect(text).toContain("sample @ develop : docs/doc-1");
    expect(text).toContain("> 一覧のページングは先頭から数えます");
    expect(text).toContain("ページングの数え方を確認したい");
    expect(text.indexOf("文書 1 › 概要")).toBeLessThan(text.indexOf("文書 2 › 冒頭"));
  });

  // 選んだコメントが 0 件のとき押せない（正常系）
  test("copy_button_disabled_when_none_selected", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("checkbox", { name: "すべて選択" }).uncheck();
    await expect(panel(page).getByRole("button", { name: "選択 0 件をコピー" })).toBeDisabled();
  });

  // クリップボードに書けないとき、失敗の通知を出す（異常系）
  test("copy_button_when_clipboard_denied", async ({ page }) => {
    await openPanel(page);
    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, "writeText", {
        value: () => Promise.reject(new Error("denied")),
      });
    });
    await panel(page).getByRole("button", { name: "選択 2 件をコピー" }).click();
    await expect(page.getByText("クリップボードにコピーできませんでした。")).toBeVisible();
  });
});

test.describe("Issue を作成", () => {
  const openPanel = async (page: Page, rows: SeedComment[] = TWO_COMMENTS) => {
    await seed(page, rows);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
  };

  // github があるとき、全文をコピーしてから Issue の作成画面を別のタブに開く（正常系）
  test("issue_button", async ({ page, context }) => {
    // 準備
    await context.route("https://github.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<title>new issue</title>" }),
    );
    await openPanel(page);
    // 実行
    const popup = page.waitForEvent("popup");
    await panel(page).getByRole("button", { name: "Issue を作成" }).click();
    // 検証
    const url = new URL((await popup).url());
    expect(url.origin + url.pathname).toBe("https://github.com/shuhei1101/dev-docs/issues/new");
    expect(url.searchParams.get("labels")).toBe("docs");
    expect(url.searchParams.get("body")).toContain("### 文書 1 › 概要");
    await expect(page.getByText("Issue の作成画面を別のタブで開きました。")).toBeVisible();
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text).toContain("ページングの数え方を確認したい");
  });

  // github が無い配信元では出さない（正常系）
  test("issue_button_hidden_without_github", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, github: null }) }),
    });
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await expect(panel(page).getByRole("button", { name: "Issue を作成" })).toHaveCount(0);
  });

  // 選んだコメントが 0 件のとき押せない（正常系）
  test("issue_button_disabled_when_none_selected", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("checkbox", { name: "すべて選択" }).uncheck();
    await expect(panel(page).getByRole("button", { name: "Issue を作成" })).toBeDisabled();
  });

  // URL が上限を超えるとき、本文の末尾を切り詰めて開き、全文はクリップボードに残す（正常系）
  test("issue_button_when_url_too_long", async ({ page, context }) => {
    // 準備
    await context.route("https://github.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<title>new issue</title>" }),
    );
    await openPanel(page, [
      { ...TWO_COMMENTS[0], body: "長い本文。".repeat(3000) },
    ]);
    // 実行
    const popup = page.waitForEvent("popup");
    await panel(page).getByRole("button", { name: "Issue を作成" }).click();
    // 検証
    const opened = await popup;
    expect(opened.url().length).toBeLessThanOrEqual(7200);
    expect(new URL(opened.url()).searchParams.get("body")).toContain(
      "…（長さの上限を超えたため、本文の末尾を切り詰めました。全文はクリップボードにコピーしています）",
    );
    await expect(
      page.getByText("本文が長いため末尾を切り詰め、全文をクリップボードにコピーしました。"),
    ).toBeVisible();
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text.length).toBeGreaterThan(15000);
  });
});

test.describe("コメントが無いことの表示", () => {
  // 溜めたコメントが無いとき、追加の仕方を出す（正常系）
  test("comment_empty_message", async ({ page }) => {
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await expect(panel(page).getByText("コメントはありません。本文の文字列を選ぶと追加できます。")).toBeVisible();
  });
});

test.describe("通知", () => {
  // 画面の右下に通知を出す（正常系）
  test("toast_position", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("button", { name: "選択 2 件をコピー" }).click();
    const toast = page.getByText("選択 2 件をクリップボードにコピーしました。");
    await expect(toast).toBeVisible();
    const box = await boxOf(toast);
    const size = viewportOf(page);
    expect(box.x).toBeGreaterThan(size.width / 2);
    expect(box.y).toBeGreaterThan(size.height / 2);
  });
});

test.describe("検索のダイアログ", () => {
  // 検索を開き、結果の選択で rev を保ったその文書を開く（正常系）
  test("search_dialog_result_select", async ({ page }) => {
    // 準備
    const api = await openDoc(page, "/sample/docs/doc-1?rev=develop");
    // 実行
    await page.getByRole("button", { name: /^検索/ }).click();
    await page.getByPlaceholder("文書を検索").fill("ページング");
    await page.getByRole("option", { name: /文書 2/ }).click();
    // 検証
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2\?rev=develop$/);
    expect(api.callsOf("search")[0]?.request.query.get("ref")).toBe("develop");
  });
});

test.describe("ショートカットの一覧", () => {
  // `?` を押すと文書の画面のキーを出す（正常系）
  test("shortcut_dialog", async ({ page }) => {
    await openDoc(page);
    await page.keyboard.press("Shift+/");
    const dialog = page.getByRole("dialog", { name: "キーボードのショートカット" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("検索を開く")).toBeVisible();
  });
});

test.describe("キーボードのショートカット", () => {
  // Ctrl+K で検索のダイアログを開く（正常系）
  test("shortcut_ctrl_k", async ({ page }) => {
    await openDoc(page);
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toBeVisible();
  });

  // `/` で検索のダイアログを開く（正常系）
  test("shortcut_slash", async ({ page }) => {
    await openDoc(page);
    await page.keyboard.press("/");
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toBeVisible();
  });

  // 入力欄にフォーカスがあるときは 1 文字のキーを受けない（正常系）
  test("shortcut_ignored_in_input", async ({ page }) => {
    // 準備
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    // 実行
    await page.keyboard.type("/?");
    // 検証
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toHaveCount(0);
    await expect(page.getByRole("dialog", { name: "キーボードのショートカット" })).toHaveCount(0);
  });

  // ダイアログを開いているときは 1 文字のキーを受けない（正常系）
  test("shortcut_ignored_in_dialog", async ({ page }) => {
    await openDoc(page);
    await page.keyboard.press("Shift+/");
    await page.keyboard.press("/");
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toHaveCount(0);
  });

  // 1 文字のショートカットを切ったとき、`/`・`?` を受けず Ctrl+K は受ける（正常系）
  test("shortcut_single_key_off", async ({ page }) => {
    // 準備
    await page.addInitScript(() => {
      localStorage.setItem(
        "dev-docs:preferences",
        JSON.stringify({ state: { colorScheme: "system", singleKeyShortcuts: false }, version: 1 }),
      );
    });
    await openDoc(page);
    // 実行
    await page.keyboard.press("/");
    await page.keyboard.press("Shift+/");
    // 検証
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: "文書を検索" })).toBeVisible();
  });
});

test.describe("ランドマーク", () => {
  // 1280 幅の本文を表示した状態で、ランドマークの名前の重複を出さない（正常系）
  test("landmarks_unique", async ({ page }) => {
    await openRendered(page);
    const result = await new AxeBuilder({ page }).withRules(["landmark-unique"]).analyze();
    expect(result.violations.map((violation) => violation.id)).toEqual([]);
  });
});

const TERM_MARKDOWN =
  "# 文書 1\n\n## 概要\n\n作業範囲の中だけを書き換える。\n\n## 関連\n\n値は settings を見る。\n";
const ALIASES: AliasItem[] = [
  {
    id: "scope",
    name: "作業範囲",
    aliases: ["scope", "担当範囲"],
    description: "触ってよい範囲",
    aliasType: "term",
    avoid: ["担当領域"],
  },
  {
    id: "settings",
    name: "設定のリファレンス",
    aliases: ["settings"],
    description: "設定のキーの一覧",
    aliasType: "doc",
  },
];

const withAliases =
  (aliases: AliasItem[]): Handler =>
  ({ path }) => ({ body: documentResponse({ path, markdown: TERM_MARKDOWN, aliases }) });

test.describe("本文の用語のツールチップ", () => {
  // 本文の用語の語にポインターを載せると、用語の名前と意味のツールチップを出す（正常系）
  test("term_tooltip", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", { document: withAliases(ALIASES) });
    const term = page.getByRole("main").getByText("作業範囲", { exact: true });
    // 実行
    await term.hover();
    // 検証
    const tooltip = page.getByRole("tooltip");
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toContainText("用語");
    await expect(tooltip).toContainText("触ってよい範囲");
  });

  // 文書の別名の語にポインターを載せると、関連文書のツールチップを出す（正常系）
  test("term_tooltip_when_doc_alias", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", { document: withAliases(ALIASES) });
    const alias = page.getByRole("main").getByText("settings", { exact: true });
    // 実行
    await alias.hover();
    // 検証
    const tooltip = page.getByRole("group", { name: "「settings」の関連文書" });
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toContainText("設定のリファレンス");
  });

  // aliases が空のときは本文の語にツールチップを付けない（正常系）
  test("term_tooltip_when_no_aliases", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", { document: withAliases([]) });
    // 実行
    await page.getByRole("main").getByText("作業範囲の中だけを書き換える。").hover();
    // 検証
    await expect(page.getByRole("tooltip")).toHaveCount(0);
  });
});
