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
import type { AliasItem, DocumentEdit } from "@/shared/api/generated/model";

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
  await page.getByRole("dialog", { name: "コメント追加" }).getByRole("textbox").fill(body);
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

  // `refSelect` で rev を書き換えて同じ文書を再度開く（正常系）
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

  // 1 つの文書が 2 つのタブに該当するとき、後のタブを押すとそのタブを現在地にしてサイドバーを替える（正常系）
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

  // 削除された page は rev を base にして base を解除した文書を開く（正常系）
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
  // base があるとき、追加・変更・削除をアイコンで出し、削除の page に取り消し線を付ける（正常系）
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

type NavPage = { kind: "page"; title: string; path: string; items: never[]; change: "added" | "modified" | "deleted" | null };
type NavGroup = { kind: "group"; title: string; path: null; change: null; items: (NavPage | NavGroup)[] };

const navPage = (title: string, path: string, change: NavPage["change"] = null): NavPage => ({ kind: "page", title, path, items: [], change });
const navGroup = (title: string, items: NavGroup["items"]): NavGroup => ({ kind: "group", title, path: null, change: null, items });

/** group A（文書 1）・B（文書 5。base があれば変更）と 4 階層の入れ子（深い文書）を持つ文書の取得 */
const withGroups: Handler = ({ path, query }) => ({
  body: documentResponse({
    path,
    tabs: [
      {
        title: "規約",
        active: true,
        items: [
          navGroup("A", [navPage("文書 1", "docs/doc-1"), navPage("文書 2", "docs/doc-2")]),
          navGroup("B", [navPage("文書 5", "docs/doc-5", query.get("diff") === null ? null : "modified")]),
          navGroup("L1", [navGroup("L2", [navGroup("L3", [navGroup("L4", [navPage("深い文書", "docs/deep")])])])]),
        ],
      },
    ],
  }),
});

const navList = (page: Page) => page.getByRole("navigation", { name: "文書の一覧" });
const groupButton = (page: Page, name: string) => navList(page).getByRole("button", { name, exact: true });

test.describe("group の開閉ボタン", () => {
  // 開いている文書を含む group を開き、ほかの group を閉じて始める。山形のアイコンは読み上げから除外する（正常系）
  test("group_toggle_initial", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withGroups });
    await expect(groupButton(page, "A")).toHaveAttribute("aria-expanded", "true");
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "false");
    await expect(navList(page).getByRole("link", { name: "文書 5" })).toHaveCount(0);
    await expect(groupButton(page, "A").locator("svg")).toHaveAttribute("aria-hidden", "true");
  });

  // クリックで配下を折りたたむ・開き、URL は変えない（正常系）
  test("group_toggle_click", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withGroups });
    const url = page.url();

    await groupButton(page, "B").click();

    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "true");
    await expect(navList(page).getByRole("link", { name: "文書 5" })).toBeVisible();
    await groupButton(page, "A").click();
    await expect(groupButton(page, "A")).toHaveAttribute("aria-expanded", "false");
    await expect(navList(page).getByRole("link", { name: "文書 1" })).toHaveCount(0);
    expect(page.url()).toBe(url);
  });

  // Enter・Space で配下を折りたたむ・開く（正常系）
  test("group_toggle_keyboard", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withGroups });
    await groupButton(page, "B").focus();

    await page.keyboard.press("Enter");
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Space");
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "false");
  });

  // 開いている文書が変わったら、利用者が閉じた group でもその文書を含む group を開く（正常系）
  test("group_opens_when_current_changed", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withGroups });
    await groupButton(page, "B").click();
    await navList(page).getByRole("link", { name: "文書 5" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-5/);
    await groupButton(page, "A").click();
    await expect(groupButton(page, "A")).toHaveAttribute("aria-expanded", "false");

    await page.goBack();

    await expect(page).toHaveURL(/\/sample\/docs\/doc-1/);
    await expect(groupButton(page, "A")).toHaveAttribute("aria-expanded", "true");
    await expect(navList(page).getByRole("link", { name: "文書 1" })).toHaveAttribute("aria-current", "page");
  });

  // 差分の表示を始めて変化のマーカーが配下に現れたら、その group を開く（正常系）
  test("group_opens_when_change_appeared", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withGroups });
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "false");

    await page.getByRole("button", { name: /リビジョンを切り替える/ }).click();
    await page.getByRole("menuitem", { name: "別のリビジョンと比較" }).click();

    await expect(page).toHaveURL(/base=7c0aa11/);
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("navigation", { name: "文書の一覧" }).getByRole("img", { name: "変更" })).toBeVisible();
  });

  // それ以外では、利用者が閉じた group を閉じたままにする（正常系）
  test("group_keeps_closed", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", { document: withGroups });
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "true");
    await groupButton(page, "B").click();

    await navList(page).getByRole("link", { name: "文書 2" }).click();

    await expect(page).toHaveURL(/\/sample\/docs\/doc-2/);
    await expect(groupButton(page, "B")).toHaveAttribute("aria-expanded", "false");
  });

  // 入れ子の階層の数を制限せず、階層ごとに字下げする（正常系）
  test("group_nested", async ({ page }) => {
    await openDoc(page, "/sample/docs/deep", { document: withGroups });
    for (const name of ["L1", "L2", "L3", "L4"]) {
      await expect(groupButton(page, name)).toHaveAttribute("aria-expanded", "true");
    }
    const deep = navList(page).getByRole("link", { name: "深い文書" });
    await expect(deep).toHaveAttribute("aria-current", "page");
    const l1 = await boxOf(groupButton(page, "L1"));
    const l4 = await boxOf(groupButton(page, "L4"));
    expect(l4.x).toBeGreaterThan(l1.x);
    expect((await boxOf(deep)).x).toBeGreaterThan(l4.x);
  });

  // 画面幅が 48rem 未満のドロワーの文書の一覧でも、group を折りたたむ・開く。ドロワーは境目と閉じるボタンを持たない（正常系）
  test("group_toggle_in_drawer", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDoc(page, "/sample/docs/doc-1", { document: withGroups });
    await page.getByRole("button", { name: "文書の一覧を開く" }).click();
    const drawer = page.getByRole("dialog", { name: "文書の一覧" });
    const b = drawer.getByRole("button", { name: "B", exact: true });
    await expect(b).toHaveAttribute("aria-expanded", "false");

    await b.click();

    await expect(b).toHaveAttribute("aria-expanded", "true");
    await expect(drawer.getByRole("link", { name: "文書 5" })).toBeVisible();
    await expect(drawer.getByRole("separator", { name: "サイドバーの幅" })).toHaveCount(0);
    await expect(drawer.getByRole("button", { name: "サイドバーを閉じる" })).toHaveCount(0);
  });
});

const sidebar = (page: Page) => page.locator("#doc-sidebar");
const separator = (page: Page) => page.getByRole("separator", { name: "サイドバーの幅" });
const titleX = async (page: Page) => (await boxOf(page.getByRole("main").getByRole("heading", { level: 1 }))).x;

test.describe("サイドバーを閉じるボタン", () => {
  // サイドバーを開いているとき、読み上げ名とツールチップ `サイドバーを閉じる` のボタンを出す（正常系）
  test("sidebar_close_button", async ({ page }) => {
    await openDoc(page);
    const button = page.getByRole("button", { name: "サイドバーを閉じる" });
    await expect(button).toHaveAttribute("aria-expanded", "true");
    await expect(button).toHaveAttribute("aria-controls", "doc-sidebar");

    await button.hover();

    await expect(page.getByText("サイドバーを閉じる", { exact: true })).toBeVisible();
  });

  // クリックでサイドバーと境目を非表示にして本文を広げ、閉じた状態をブラウザに保存する（正常系）
  test("sidebar_close", async ({ page }) => {
    await openDoc(page);
    const before = await titleX(page);

    await page.getByRole("button", { name: "サイドバーを閉じる" }).click();

    await expect(page.getByRole("navigation", { name: "文書の一覧" })).toBeHidden();
    await expect(separator(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "サイドバーを開く" })).toBeVisible();
    expect(await titleX(page)).toBeLessThan(before);
    await page.reload();
    await expect(page.getByRole("button", { name: "サイドバーを開く" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "文書の一覧" })).toBeHidden();
  });

  // 画面幅が 48rem 未満のときは出さない（正常系）
  test("sidebar_close_hidden_when_narrow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDoc(page);
    await expect(page.getByRole("button", { name: "サイドバーを閉じる" })).toBeHidden();
    await expect(separator(page)).toBeHidden();
  });
});

test.describe("サイドバーを開くボタン", () => {
  // 閉じているとき、読み上げ名 `サイドバーを開く`・`aria-expanded="false"` のボタンを出し、クリックで閉じる前の幅で開いて保存する（正常系）
  test("sidebar_open_restores_width", async ({ page }) => {
    await openDoc(page);
    await separator(page).focus();
    await page.keyboard.press("End");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "480");
    await page.getByRole("button", { name: "サイドバーを閉じる" }).click();
    const button = page.getByRole("button", { name: "サイドバーを開く" });
    await expect(button).toHaveAttribute("aria-expanded", "false");

    await button.click();

    await expect(page.getByRole("navigation", { name: "文書の一覧" })).toBeVisible();
    expect((await boxOf(sidebar(page))).width).toBe(480);
    await page.reload();
    await expect(page.getByRole("navigation", { name: "文書の一覧" })).toBeVisible();
    expect((await boxOf(sidebar(page))).width).toBe(480);
  });
});

test.describe("サイドバーの境目", () => {
  // 既定の幅 240 で始め、読み上げ名と値の範囲を持つ（正常系）
  test("separator_initial", async ({ page }) => {
    await openDoc(page);
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "240");
    await expect(separator(page)).toHaveAttribute("aria-valuemin", "192");
    await expect(separator(page)).toHaveAttribute("aria-valuemax", "480");
    expect((await boxOf(sidebar(page))).width).toBe(240);
  });

  // ドラッグで幅を変え、本文の左端をその分だけ動かし、変えた幅をブラウザに保存する（正常系）
  test("separator_drag", async ({ page }) => {
    await openDoc(page);
    const before = await titleX(page);
    const box = await boxOf(separator(page));
    const y = box.y + 40;

    await page.mouse.move(box.x + box.width / 2, y);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 80, y, { steps: 5 });
    await page.mouse.up();

    await expect(separator(page)).toHaveAttribute("aria-valuenow", "320");
    expect((await boxOf(sidebar(page))).width).toBe(320);
    expect(await titleX(page)).toBeCloseTo(before + 80, 0);
    await page.reload();
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "320");
  });

  // ドラッグで最小・最大を超えない（正常系）
  test("separator_drag_range", async ({ page }) => {
    await openDoc(page);
    const box = await boxOf(separator(page));
    const x = box.x + box.width / 2;
    const y = box.y + 40;

    await page.mouse.move(x, y);
    await page.mouse.down();
    // 画面の中で、最小（192）より 48px 以上狭くなる位置へ動かす
    await page.mouse.move(x - 100, y, { steps: 5 });
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "192");
    await page.mouse.move(x + 600, y, { steps: 5 });
    await page.mouse.up();

    await expect(separator(page)).toHaveAttribute("aria-valuenow", "480");
  });

  // ←→ で 16px、Home で最小、End で最大にする（正常系）
  test("separator_keyboard", async ({ page }) => {
    await openDoc(page);
    await separator(page).focus();

    await page.keyboard.press("ArrowRight");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "256");
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowLeft");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "224");
    await page.keyboard.press("Home");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "192");
    await page.keyboard.press("End");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "480");
  });

  // ダブルクリックで既定の幅（240）に戻す（正常系）
  test("separator_double_click", async ({ page }) => {
    await openDoc(page);
    await separator(page).focus();
    await page.keyboard.press("End");

    await separator(page).dblclick();

    await expect(separator(page)).toHaveAttribute("aria-valuenow", "240");
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

  // 文書の無いタブでは `{配信元の ID}` / `{タブ名}` だけを出し、タブ名をリンクにしない（正常系）
  test("breadcrumb_when_empty_tab", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, tabs: TABS_WITH_DOCS }) }),
    });
    await page.getByRole("button", { name: "空" }).click();
    const crumb = page.getByRole("navigation", { name: "パンくず" });
    await expect(crumb.getByRole("listitem")).toHaveText(["sample", "空"]);
    await expect(crumb.getByRole("link")).toHaveText(["sample"]);
    await expect(crumb.getByText("空")).toHaveAttribute("aria-current", "page");
  });
});

test.describe("文書のタイトル", () => {
  // 文書の名前を見出し 1 に出す（正常系）
  test("doc_title", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-2");
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("文書 2");
  });

  // 文書のタイトルを mdmark の見出し 1 と同じ大きさ・太さで出し、下に区切り線を表示する（正常系）
  test("doc_title_matches_mdmark_h1", async ({ page }) => {
    // 準備
    await openRendered(page);
    // 実行
    const title = await page.getByRole("main").getByRole("heading", { level: 1 }).evaluate((h1) => {
      const body = document.querySelector(".mdmark");
      const s = getComputedStyle(h1);
      // 区切り線は、タイトルと編集のボタンを並べる行の下に引く
      const row = h1.parentElement === null ? s : getComputedStyle(h1.parentElement);
      return {
        fontSize: parseFloat(s.fontSize),
        bodyFontSize: body === null ? 0 : parseFloat(getComputedStyle(body).fontSize),
        fontWeight: s.fontWeight,
        borderBottomWidth: row.borderBottomWidth,
        borderBottomStyle: row.borderBottomStyle,
      };
    });
    // 検証
    expect(title.fontSize).toBeCloseTo(title.bodyFontSize * 1.9, 1);
    expect(title.fontWeight).toBe("700");
    expect(title.borderBottomWidth).toBe("1px");
    expect(title.borderBottomStyle).toBe("solid");
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
  // 取得が 1 秒を超えたときだけ、タイトル・情報・本文のスケルトンを出す（正常系）
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
  // 選択肢はリビジョンのメニューと同じ並びで、一覧に無い base は先頭に追加する。再選択すると base を書き換える（正常系）
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
  // 開いているリビジョンを初期値にし、再選択すると rev を書き換える（正常系）
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
  // クリックで base を解除した同じ文書を開き、マーカーを削除する（正常系）
  test("diff_clear", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    await page.getByRole("button", { name: "差分の強調を解除" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1$/);
    await expect(page.getByRole("region", { name: "差分" })).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "文書の一覧" }).getByRole("img")).toHaveCount(0);
  });

  // base を解除したら、本文の差分の強調を解除する（正常系）
  test("diff_clear_body", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    await expect(page.locator(".mdmark-diff-block")).not.toHaveCount(0);
    await page.getByRole("button", { name: "差分の強調を解除" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1$/);
    await expect(page.locator(".mdmark-diff-block")).toHaveCount(0);
    await expect(page.getByText("変更後の本文")).toBeVisible();
  });
});

test.describe("文書の本文の差分", () => {
  const block = (page: Page, kind: "add" | "del") =>
    page.locator(`.mdmark-diff-block[data-kind="${kind}"]`);

  // base があるときは比較元の本文と比べ、変わったブロックを本文の中で強調する（正常系）
  test("body_diff_highlight", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    await expect(block(page, "add")).toContainText("変更後の本文");
    await expect(page.locator(".mdmark-diff-block").filter({ hasText: "同じ本文" })).toHaveCount(0);
  });

  // 比較元にだけあるブロックを、削除したブロックとして本文の中で強調する（正常系）
  test("body_diff_highlight_when_block_deleted", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1?base=7c0aa11", {
      document: ({ path, query }) => {
        const before = query.get("diff") === null && query.get("ref") === "7c0aa11";
        return {
          body: documentResponse({
            path,
            ref: before ? "7c0aa11" : "develop",
            markdown: `# 文書 1\n\n## 概要\n\n同じ本文\n\n${before ? "削除した本文\n\n" : ""}## 関連\n\n末尾の本文\n`,
            diff: before ? null : { base: "7c0aa11", change: "modified", changedItems: ["概要"] },
          }),
        };
      },
    });
    await expect(block(page, "del")).toContainText("削除した本文");
    await expect(page.locator(".mdmark-diff-block").filter({ hasText: "同じ本文" })).toHaveCount(0);
  });

  // base が無いときは強調しない（正常系）
  test("body_diff_highlight_without_base", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1", { document: withDiff });
    await expect(page.getByText("変更後の本文")).toBeVisible();
    await expect(page.locator(".mdmark-diff-block")).toHaveCount(0);
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

  // YAML を読み込めないとき、ファイル/場所/原因の一覧を出す（正常系）
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
  // クリックで同じ条件の文書の取得を再度呼び出す（正常系）
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

  // 本文の幅は画面の幅から左右の余白・サイドバー・間隔を除いた幅で、広い画面でも上限を持たない（正常系）
  for (const width of [1920, 2880]) {
    test(`body_width_without_upper_limit_${width}`, async ({ page }) => {
      // 準備
      await page.setViewportSize({ width, height: 1080 });
      await openRendered(page);

      // 実行
      const box = await boxOf(page.getByRole("main"));
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);

      // 検証（左右の余白 16px ずつ・サイドバー 240px・間隔 24px）
      expect(box.width).toBeCloseTo(clientWidth - 296, 0);
    });
  }

  // 本文には画面の基本のスタイル（Tailwind の Preflight）を当てず、単独の mdmark と同じ見た目で描く（正常系）
  test("body_without_preflight", async ({ page }) => {
    // 準備
    const markdown = [
      "# 文書 1",
      "",
      "## 概要",
      "",
      "- 項目 1",
      "- 項目 2",
      "",
      "#### 見出し 4",
      "",
      "```bash",
      "dev-docs serve",
      "```",
      "",
      '<!-- map: {"title": "フロー"} -->',
      "",
      "```mermaid",
      "sequenceDiagram",
      "  participant A as 画面",
      "  participant B as サーバー",
      "  A->>B: 要求",
      "  B-->>A: 応答",
      "```",
      "",
      "<!-- /map -->",
      "",
    ].join("\n");
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, markdown }) }),
    });
    // map の図は見出しより後に描き終わるため、閉じた凡例が描かれるまで待つ
    await expect(page.locator(".mdmark .mdmark-diagram-legend[hidden]")).toBeAttached();
    // 実行
    const styles = await page.locator(".mdmark").evaluate((body) => {
      const style = (selector: string, pseudo: string | null = null) => {
        const element = body.querySelector(selector);
        return element === null ? null : getComputedStyle(element, pseudo);
      };
      return {
        listStyle: style("ul:not([class]) > li")?.listStyleType,
        h4Weight: style("h4")?.fontWeight,
        h4MarginBottom: style("h4")?.marginBottom,
        preFont: style("pre")?.fontFamily,
        boxSizing: style("p, li")?.boxSizing,
        beforeBoxSizing: style("h2", "::before")?.boxSizing,
        hiddenLegend: style(".mdmark-diagram-legend[hidden]")?.display,
      };
    });
    // 検証
    expect(styles.listStyle).toBe("disc");
    expect(styles.h4Weight).toBe("700");
    expect(styles.h4MarginBottom).not.toBe("0px");
    expect(styles.preFont).toBe("monospace");
    expect(styles.boxSizing).toBe("content-box");
    expect(styles.beforeBoxSizing).toBe("content-box");
    // mdmark が hidden を付けて表示する要素は、mdmark の値で描く（Preflight の [hidden] の !important を当てない）
    expect(styles.hiddenLegend).toBe("flex");
  });

  // 本文の外（文書の一覧）には画面の基本のスタイルを当てたままにする（正常系）
  test("frame_keeps_preflight", async ({ page }) => {
    // 準備
    await openRendered(page);
    // 実行
    const sidebarList = await page
      .getByRole("navigation", { name: "文書の一覧" })
      .locator("ul")
      .first()
      .evaluate((ul) => ({ listStyle: getComputedStyle(ul).listStyleType, boxSizing: getComputedStyle(ul).boxSizing }));
    const hiddenDisplay = await page.getByRole("navigation", { name: "文書の一覧" }).evaluate((nav) => {
      const hidden = document.createElement("ul");
      hidden.className = "mdmark-diagram-legend";
      hidden.hidden = true;
      nav.append(hidden);
      return getComputedStyle(hidden).display;
    });
    // 検証
    expect(sidebarList).toEqual({ listStyle: "none", boxSizing: "border-box" });
    expect(hiddenDisplay).toBe("none");
  });

  // 本文の左端をパンくず・文書のタイトルと同じ位置にし、本文の左右と上に余白を置かない（正常系）
  test("body_left_aligned_with_title", async ({ page }) => {
    // 準備
    await openRendered(page);
    // 実行
    const title = await boxOf(page.getByRole("main").getByRole("heading", { level: 1 }));
    const paragraph = await boxOf(page.locator(".mdmark p").first());
    const padding = await page.locator(".mdmark").evaluate((body) => {
      const s = getComputedStyle(body);
      return [s.paddingTop, s.paddingLeft, s.paddingRight];
    });
    // 検証
    expect(Math.round(paragraph.x)).toBe(Math.round(title.x));
    expect(padding).toEqual(["0px", "0px", "0px"]);
  });

  // 同じ配信元の文書へのリンクは、画面を再読み込みせず rev を保って開く（正常系）
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

  // mdmark が Mermaid の図の click のノードをリンクにしたものも、本文のリンクと同じく rev を保って開く（正常系）
  test("body_mermaid_click_link", async ({ page }) => {
    // 準備
    const markdown = [
      "# 文書 1",
      "",
      "## 概要",
      "",
      "```mermaid",
      "classDiagram",
      "  class 受付",
      '  click 受付 href "./doc-2"',
      "```",
      "",
    ].join("\n");
    await openRendered(page, "/sample/docs/doc-1?rev=develop", {
      document: ({ path }) => ({ body: documentResponse({ path, markdown }) }),
    });
    const node = page.locator('.mdmark a[href="./doc-2"]:visible');
    await expect(node).toHaveCount(1);
    // 実行
    await node.click();
    // 検証
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2\?rev=develop$/);
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

  // `table.pin_default` を指定せず、横にはみ出す表も描いた直後はどの列も留めない（正常系）
  test("body_table_no_pinned_column_initially", async ({ page }) => {
    // 準備
    const columns = Array.from({ length: 12 }, (_, i) => `列 ${i + 1}`);
    const markdown = [
      "# 文書 1",
      "",
      "## 概要",
      "",
      '<!-- table: {"kind": "data"} -->',
      "",
      `| ${columns.join(" | ")} |`,
      `| ${columns.map(() => "---").join(" | ")} |`,
      ...Array.from({ length: 3 }, (_, row) => `| ${columns.map((name) => `${name} の ${row + 1} 行目の長い値です`).join(" | ")} |`),
      "",
      "<!-- /table -->",
      "",
    ].join("\n");
    await page.setViewportSize({ width: 1280, height: 800 });
    // 実行
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, markdown }) }),
    });
    await expect(page.getByRole("columnheader", { name: /^列 1 / })).toBeVisible();
    // 検証（表が横にはみ出している）
    const table = page.locator(".mdmark table").first();
    await expect
      .poll(() => table.evaluate((element) => element.scrollWidth > (element.parentElement?.clientWidth ?? 0)))
      .toBe(true);
    // 検証（ピン止めの機能を持つ表で、どの列も留めていない）
    await expect(page.locator(".mdmark .mdmark-pin")).not.toHaveCount(0);
    await expect(page.locator(".mdmark .is-pinned-col")).toHaveCount(0);
    await expect(page.locator('.mdmark .mdmark-pin[aria-pressed="true"]')).toHaveCount(0);
  });
});

test.describe("列の表示のメニュー", () => {
  /** 列の表示・非表示の機能を持つ表の、見出し行の右上の表のメニューのボタン（`index` は出る順） */
  const tableMenu = (page: Page, index = 0) => page.getByRole("button", { name: /^表のメニュー/ }).nth(index);

  /** 表のメニューを開き、`テーブル設定` の項目でパネルを開く */
  const openTableSettings = async (page: Page, index = 0) => {
    await tableMenu(page, index).click();
    await page.getByRole("button", { name: "テーブル設定", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "テーブル設定" })).toBeVisible();
  };

  // `+columns` の表に表のメニューのボタンを出し、メニューに `テーブル設定` の項目を並べる（正常系）
  test("columns_menu_visible", async ({ page }) => {
    await openRendered(page);
    await expect(page.getByRole("button", { name: "表のメニュー", exact: true })).toBeVisible();
    await tableMenu(page).click();
    await expect(page.getByRole("button", { name: "テーブル設定", exact: true })).toBeVisible();
  });

  // 先頭の列は隠せない（正常系）
  test("columns_menu_first_column_locked", async ({ page }) => {
    await openRendered(page);
    await openTableSettings(page);
    const dialog = page.getByRole("dialog", { name: "テーブル設定" });
    await expect(dialog.getByRole("button", { name: "「キー」を隠す" })).toBeDisabled();
    await expect(dialog.getByText("先頭の列は隠せません")).toBeVisible();
  });

  // 隠した列を表から除き、件数を表のメニューのボタンのスクリーンリーダー向けの名前に添える（正常系）
  test("columns_menu_hidden_columns", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, columns: { [TABLE_KEY]: ["備考"] } }),
      }),
    });
    await expect(page.locator("th:visible")).toHaveText(["キー", "名称"]);
    await expect(page.getByRole("button", { name: "表のメニュー（1 列を非表示）", exact: true })).toBeVisible();
  });

  // 列の出し入れのたびに、その表の隠した列を保存する（正常系）
  test("columns_menu_save", async ({ page }) => {
    // 準備
    const api = await openRendered(page);
    await openTableSettings(page);
    // 実行
    await page.getByRole("dialog", { name: "テーブル設定" }).getByRole("button", { name: "「備考」を隠す" }).click();
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
    await openTableSettings(page);
    // 実行
    await page.getByRole("dialog", { name: "テーブル設定" }).getByRole("button", { name: "「備考」を隠す" }).click();
    // 検証
    await expect(page.getByText("列の表示を保存できませんでした。")).toBeVisible();
    await expect(page.locator("th:visible")).toHaveText(["キー", "名称"]);
  });

  // `+columns` でない表を挟んでも、onColumnsChange の表の番号を `+columns` の表のキーにして保存する（正常系）
  test("columns_menu_save_when_tables_mixed", async ({ page }) => {
    // 準備（1 つ目は `+columns` でない表、2・3 つ目が `+columns` の表）
    const table = (marker: string, head: string) =>
      [marker, "", `| ${head} | 名称 | 備考 |`, "| --- | --- | --- |", "| k1 | 名称 1 | 備考 1 |", "", "<!-- /table -->", ""].join("\n");
    const markdown = [
      "# 文書 1",
      "",
      "## 概要",
      "",
      table("<!-- table: data -->", "固定"),
      table("<!-- table: data +columns -->", "表 A"),
      table("<!-- table: data +columns -->", "表 B"),
    ].join("\n");
    const api = await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, markdown, tableKeys: ["sample:fixed", "sample:a", "sample:b"] }),
      }),
    });
    // 実行（3 つ目の表の表のメニューの `テーブル設定` で備考を隠す）
    await openTableSettings(page, 1);
    await page.getByRole("dialog", { name: "テーブル設定" }).getByRole("button", { name: "「備考」を隠す" }).click();
    // 検証
    await expect.poll(() => api.callsOf("putColumns").length).toBe(1);
    expect(api.callsOf("putColumns")[0]?.request.body).toEqual({
      table: "sample:b",
      hidden: ["備考"],
    });
  });

  // JSON のマーカーの表: 保存した隠す列でマーカーの隠す列を置き換え、複数行のマーカーの表も表の番号に数える（正常系）
  test("columns_menu_json_marker", async ({ page }) => {
    // 準備（1 つ目は備考を最初から隠す JSON のマーカー、2 つ目は列の表示の機能を持つ複数行の JSON のマーカー）
    const table = (marker: string, head: string) =>
      [marker, "", `| ${head} | 名称 | 備考 |`, "| --- | --- | --- |", "| k1 | 名称 1 | 備考 1 |", "", "<!-- /table -->", ""].join("\n");
    const markdown = [
      "# 文書 1",
      "",
      "## 概要",
      "",
      table('<!-- table: {"kind": "data", "columns": {"備考": {"hidden": true}}} -->', "表 A"),
      table('<!-- table: {\n  "kind": "data",\n  "features": {"columns": {}}\n} -->', "表 B"),
    ].join("\n");
    const api = await openRendered(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, markdown, tableKeys: ["sample:a", "sample:b"], columns: { "sample:a": [] } }),
      }),
    });
    // 検証（保存した隠す列が空の表 A は、マーカーで隠した備考も表示する）
    await expect(page.locator("th:visible")).toHaveText(["表 A", "名称", "備考", "表 B", "名称", "備考"]);
    // 実行（2 つ目の表の表のメニューの `テーブル設定` で備考を隠す）
    await openTableSettings(page, 1);
    await page.getByRole("dialog", { name: "テーブル設定" }).getByRole("button", { name: "「備考」を隠す" }).click();
    // 検証
    await expect.poll(() => api.callsOf("putColumns").length).toBe(1);
    expect(api.callsOf("putColumns")[0]?.request.body).toEqual({
      table: "sample:b",
      hidden: ["備考"],
    });
  });
});

test.describe("目次", () => {
  /** mdmark が本文に描く右側の目次のブロック */
  const sideToc = (page: Page) => page.getByRole("navigation", { name: "右側の目次", includeHidden: true });

  /** 右側の目次を出す（既定の hover の出し方で、右端の線を指す） */
  const openSideToc = async (page: Page) => {
    await page.locator(".mdmark-side-toc-rail").hover();
    await expect(sideToc(page)).toBeVisible();
  };

  // mdmark の右側の目次だけを出し、本文の右の列に別の目次を配置しない。線を指すと本文の見出しが並ぶ（正常系）
  test("toc_items", async ({ page }) => {
    await openRendered(page);
    await expect(sideToc(page)).toHaveCount(1);
    await expect(page.getByRole("navigation", { name: "目次", exact: true, includeHidden: true })).toHaveCount(0);
    await openSideToc(page);
    await expect(sideToc(page).getByRole("link")).toHaveText(["概要", "項目", "項目の表", "関連"]);
  });

  // 比較中は、比較元から変わったセクションの項目にだけ変更のマーカーを出す（正常系）
  test("toc_change_marker", async ({ page }) => {
    await openRendered(page, "/sample/docs/doc-1?base=7c0aa11", { document: withDiff });
    await openSideToc(page);
    await expect(sideToc(page).getByRole("link", { name: "概要（変更）" })).toHaveCount(1);
    await expect(sideToc(page).getByRole("link", { name: "関連", exact: true })).toHaveCount(1);
  });

  // 画面の中で別の文書へ移ると、移った先の文書の見出しで目次を再描画する（正常系）
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
    await expect(sideToc(page).getByRole("link", { includeHidden: true })).toHaveText(["概要", "関連"]);
    // 実行
    await page
      .getByRole("navigation", { name: "文書の一覧" })
      .getByRole("link", { name: "文書 2" })
      .click();
    // 検証
    await expect(page.getByRole("heading", { level: 2, name: "別の概要" })).toBeVisible();
    await expect(sideToc(page).getByRole("link", { includeHidden: true })).toHaveText(["別の概要", "別の関連"]);
  });

  // 本文に見出し 1〜3 が無いときは出さない（正常系）
  test("toc_hidden_without_headings", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, markdown: "# 文書 1\n\n見出しの無い本文です。\n" }),
      }),
    });
    await expect(page.getByText("見出しの無い本文です。")).toBeVisible();
    await expect(sideToc(page)).toHaveCount(0);
  });

  // 目次の見出しのクリックでその見出しへ移る（正常系）
  test("toc_click", async ({ page }) => {
    await openRendered(page);
    await openSideToc(page);
    await sideToc(page).getByRole("link", { name: "関連" }).click();
    await expect(page).toHaveURL(/#関連$|#%E9%96%A2%E9%80%A3$/);
  });

  /** 画面を下へスクロールできる長さの本文 */
  const LONG_MARKDOWN = `# 文書 1\n\n${Array.from(
    { length: 30 },
    (_, index) => `## セクション ${index + 1}\n\n${"長い本文の段落です。".repeat(40)}\n`,
  ).join("\n")}`;

  /** 長い本文を開き、下へ 1400px スクロールする */
  const openScrolled = async (page: Page) => {
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, markdown: LONG_MARKDOWN }) }),
    });
    await expect(page.getByRole("heading", { level: 2, name: /^セクション 1 / })).toBeVisible();
    await page.locator("#doc-scroll").hover();
    await page.mouse.wheel(0, 1400);
    await expect
      .poll(() => page.locator("#doc-scroll").evaluate((element) => element.scrollTop))
      .toBeGreaterThanOrEqual(1400);
  };

  /** 種類のタブの下端（画面の上端からの px） */
  const tabsBottom = async (page: Page) => {
    const box = await boxOf(page.getByRole("navigation", { name: "文書の種類" }));
    return box.y + box.height;
  };

  // スクロールしても、右端の線と目次の枠を本文の領域の上端（トップバーと種類のタブの下）に固定する（正常系）
  test("toc_below_tabs_when_scrolled", async ({ page }) => {
    // 準備
    await openScrolled(page);
    const bottom = await tabsBottom(page);
    const rail = await boxOf(page.locator(".mdmark-side-toc-rail"));
    // 実行（開いた目次の枠が右端の線に重なるため、線の位置へポインターを移して出す）
    await page.mouse.move(rail.x + rail.width / 2, rail.y + rail.height / 2);
    await expect(sideToc(page)).toBeVisible();
    // 検証
    expect(rail.y).toBeGreaterThanOrEqual(bottom);
    expect((await boxOf(sideToc(page))).y).toBeGreaterThanOrEqual(bottom);
  });

  /** 画面を下へスクロールできる長さの、本文の行の多い表を持つ本文 */
  const LONG_TABLE_MARKDOWN = `# 文書 1\n\n## 概要\n\n${"表の前の段落です。".repeat(80)}\n\n| 名前 | 値 |\n| --- | --- |\n${Array.from(
    { length: 60 },
    (_, index) => `| 行 ${index + 1} | 値 ${index + 1} |`,
  ).join("\n")}\n\n${"表の後の段落です。".repeat(200)}\n`;

  /** iPad Pro 11 の縦の画面幅で、本文の行の多い表を持つ文書を開く。`withoutTimeline` のときはスクロール連動のアニメーションを持たないブラウザとして開く */
  const openLongTable = async (page: Page, { withoutTimeline }: { withoutTimeline: boolean }) => {
    if (withoutTimeline) {
      await page.addInitScript(() => {
        const supports = CSS.supports.bind(CSS);
        CSS.supports = (...args: Parameters<typeof CSS.supports>) =>
          String(args[0]).includes("animation-timeline") ? false : supports(...args);
      });
    }
    await page.setViewportSize({ width: 834, height: 1194 });
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({ body: documentResponse({ path, markdown: LONG_TABLE_MARKDOWN }) }),
    });
    await expect(page.getByRole("columnheader", { name: "名前" })).toBeVisible();
  };

  /** 本文の領域（スクロールの容器）の上端（画面の上端からの px） */
  const scrollTop = async (page: Page) => (await boxOf(page.locator("#doc-scroll"))).y;

  /** 表の上端（本文の領域の内容の上端からの px） */
  const tableTop = (page: Page) =>
    page.locator(".mdmark table").first().evaluate((table) => {
      const container = document.getElementById("doc-scroll") as HTMLElement;
      return table.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop;
    });

  /** 本文の領域を指定の位置までスクロールする */
  const scrollBodyTo = (page: Page, y: number) =>
    page.locator("#doc-scroll").evaluate((element, top) => element.scrollTo(0, top), y);

  /** 表の見出し行の上端（画面の上端からの px） */
  const headTop = async (page: Page) => (await boxOf(page.getByRole("columnheader", { name: "名前" }))).y;

  /** mdmark が見出し行を留める位置（本文の領域の上端からの px）。`--mdmark-sticky-top` の計算値 */
  const stickyTop = (page: Page) =>
    page.locator(".mdmark").first().evaluate((body) => Number.parseFloat(getComputedStyle(body).getPropertyValue("--mdmark-sticky-top")));

  for (const withoutTimeline of [false, true]) {
    const suffix = withoutTimeline ? "_without_timeline" : "";
    // 表の上端が本文の領域の上端（トップバーと種類のタブの下）に達するまでは見出し行を表の中に置き、達した後はその上端に留める（正常系）
    test(`table_head_below_tabs_when_scrolled${suffix}`, async ({ page }) => {
      // 準備
      await openLongTable(page, { withoutTimeline });
      const sticky = await stickyTop(page);
      expect(sticky).toBe(0);
      const expected = (await scrollTop(page)) + sticky;
      expect(expected).toBeGreaterThanOrEqual(await tabsBottom(page));
      const top = await tableTop(page);
      // 実行（表の上端を留める位置より 300px 下に置く）
      await scrollBodyTo(page, top - sticky - 300);
      // 検証
      await expect.poll(async () => Math.abs((await headTop(page)) - expected - 300)).toBeLessThanOrEqual(1);
      // 実行（表の上端を留める位置より 400px 上へ過ぎさせる）
      await scrollBodyTo(page, top - sticky + 400);
      // 検証
      await expect.poll(async () => Math.abs((await headTop(page)) - expected)).toBeLessThanOrEqual(1);
    });
  }

  // 画面幅が 48rem 未満でも、スクロールした右側の目次をトップバーと種類のタブの下に固定する（正常系）
  test("toc_below_tabs_when_scrolled_narrow", async ({ page }) => {
    // 準備
    await page.setViewportSize({ width: 390, height: 844 });
    // 実行
    await openScrolled(page);
    // 検証
    const bottom = await tabsBottom(page);
    expect((await boxOf(page.locator(".mdmark-side-toc"))).y).toBeGreaterThanOrEqual(bottom);
  });
});

test.describe("コメントの追加", () => {
  // 本文の文字列を選んで保存すると、コメントを溜め、パネルを開いて一覧とトップバーの件数を再描画する（正常系）
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

  // 同じ文書のコメントは、本文のそのマーカーが画面に入るまでスクロールして強調する（正常系）
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
    await expect(mark(page, "文書 1 の末尾の文")).toHaveAttribute("data-focused");
  });

  // マーカーが見つからないまま別の文書へ移ったら、後で元の文書を再度開いて同じ文字列のマーカーが付いてもスクロールしない（正常系）
  test("place_scroll_cleared_when_doc_left", async ({ page }) => {
    // 準備（同じ文字列が 2 か所あり、前後の文字列が合わないため、場所を選んだ時点ではマーカーが付かない）
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
    // 実行（文書 1 へ移り、文書 2 を再度開いて、1 つ目の「中ほどの文」を画面の上端に配置してコメントを付ける）
    await sidebar.getByRole("link", { name: "文書 1" }).click();
    await expect(heading).toHaveText("文書 1");
    await sidebar.getByRole("link", { name: "文書 2" }).click();
    await expect(heading).toHaveText("文書 2");
    const target = page.getByText("中ほどの文").first();
    await target.evaluate((element) => element.scrollIntoView({ block: "start" }));
    const bodyScroll = () => page.locator("#doc-scroll").evaluate((element) => element.scrollTop);
    const before = await bodyScroll();
    await expect(page.locator("#mdmark-comment-hint")).toBeAttached();
    await target.selectText();
    await page.getByRole("button", { name: "コメント", exact: true }).click();
    await page.getByRole("dialog", { name: "コメント追加" }).getByRole("textbox").fill("開き直した後の確認");
    await page.getByRole("button", { name: "コメントを保存" }).click();
    // 検証
    await expect(mark(page, "中ほどの文")).toHaveCount(1);
    await page.waitForTimeout(500);
    expect(Math.abs((await bodyScroll()) - before)).toBeLessThan(5);
  });

  // 他の文書のコメントは、その文書を開いた後に本文のマーカーが画面に入るまでスクロールして強調する（正常系）
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
    await expect(mark(page, "文書 2 の末尾の文")).toHaveAttribute("data-focused");
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
  // 記載したコメントを出す（正常系）
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

  // 保存で本文を書き込む（正常系）
  test("edit_save", async ({ page }) => {
    await openPanel(page);
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await panel(page).getByRole("textbox", { name: "コメント" }).fill("直した本文");
    await panel(page).getByRole("button", { name: "保存" }).click();
    await expect(panel(page).getByText("直した本文")).toBeVisible();
    await expect(panel(page).getByRole("textbox")).toHaveCount(0);
  });

  // 保存しても、本文のマーカーが消えない（正常系）
  test("edit_save_redraws_mark", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openRendered(page);
    const mark = page.locator(".mdmark-comment-mark").filter({ hasText: "一覧のページングは先頭から数えます" });
    await expect(mark).toHaveCount(1);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("button", { name: "修正" }).first().click();
    await panel(page).getByRole("textbox", { name: "コメント" }).fill("修正した本文");
    await panel(page).getByRole("button", { name: "保存" }).click();
    await expect(panel(page).getByText("修正した本文")).toBeVisible();
    await expect(mark).toHaveCount(1);
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
  // クリックでそのコメントを削除し、一覧と件数を再描画する（正常系）
  test("delete_button", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openDoc(page);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("button", { name: "削除" }).first().click();
    await expect(panel(page).getByRole("listitem")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "コメント 1 件" })).toBeVisible();
  });

  // 削除したコメントの本文のマーカーを、mdmark の reloadComments で再描画して削除する（正常系）
  test("delete_button_redraws_mark", async ({ page }) => {
    await seed(page, TWO_COMMENTS);
    await openRendered(page);
    await expect(page.locator(".mdmark-comment-mark")).toHaveCount(1);
    await page.getByRole("button", { name: /^コメント \d+ 件$/ }).click();
    await panel(page).getByRole("listitem").filter({ hasText: "ページングの数え方を確認したい" }).getByRole("button", { name: "削除" }).click();
    await expect(panel(page).getByRole("listitem")).toHaveCount(1);
    await expect(page.locator(".mdmark-comment-mark")).toHaveCount(0);
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

  // クリップボードに書き込めないとき、失敗の通知を出す（異常系）
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
  // 本文の用語の単語にポインターを合わせると、用語の名前と意味のツールチップを出す（正常系）
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

  // 文書の別名の単語にポインターを合わせると、関連文書のツールチップを出す（正常系）
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

  // aliases が空のときは本文の単語にツールチップを付けない（正常系）
  test("term_tooltip_when_no_aliases", async ({ page }) => {
    // 準備
    await openRendered(page, "/sample/docs/doc-1", { document: withAliases([]) });
    // 実行
    await page.getByRole("main").getByText("作業範囲の中だけを書き換える。").hover();
    // 検証
    await expect(page.getByRole("tooltip")).toHaveCount(0);
  });
});

test.describe("project-index から文書を受け取れないときの表示", () => {
  // 文書の取得が 503 のとき、接続先と理由を画面全体のアラートに出し、再読み込みで取得を再度呼び出す（異常系）
  test("project_index_unreachable_alert", async ({ page }) => {
    // 準備
    const api = await mockApi(page, {
      document: () =>
        problem(503, {
          detail: "project-index（http://127.0.0.1:8786）に接続できませんでした。接続を拒否されました（Connection refused）",
          projectIndex: {
            address: "http://127.0.0.1:8786",
            reason: "接続を拒否されました（Connection refused）",
          },
        }),
    });
    // 実行
    await page.goto("/sample/docs/doc-1");
    const alert = page.getByRole("alert").filter({ hasText: "project-index に接続できませんでした" });
    await expect(alert).toBeVisible();
    const before = api.callsOf("document").length;
    await alert.getByRole("button", { name: "再読み込み" }).click();
    // 検証
    await expect(alert).toContainText("project-index を起動してから、再読み込みしてください。");
    await expect(alert.locator("dd")).toHaveText([
      "http://127.0.0.1:8786",
      "接続を拒否されました（Connection refused）",
    ]);
    await expect.poll(() => api.callsOf("document").length).toBeGreaterThan(before);
  });

  // 文書の取得が 503 の timeout のとき、応答が無かった見出しと説明を出す（異常系）
  test("project_index_timeout_alert", async ({ page }) => {
    // 準備
    await mockApi(page, {
      document: () =>
        problem(503, {
          detail: "project-index（http://127.0.0.1:8786）から応答がありませんでした。70 秒以内に応答がありませんでした",
          projectIndex: {
            address: "http://127.0.0.1:8786",
            reason: "70 秒以内に応答がありませんでした",
            kind: "timeout",
          },
        }),
    });
    // 実行
    await page.goto("/sample/docs/doc-1");
    // 検証
    const alert = page.getByRole("alert").filter({ hasText: "project-index から応答がありませんでした" });
    await expect(alert).toContainText(
      "project-index が配信元を初めて読み込む間は、時間がかかることがあります。しばらく待ってから、再読み込みしてください。",
    );
    await expect(alert.locator("dd")).toHaveText([
      "http://127.0.0.1:8786",
      "70 秒以内に応答がありませんでした",
    ]);
  });

  // 文書の取得が 502 のとき、処理に失敗した見出しと説明と project-index の理由を出し、スマホ幅で長い理由を折り返す（異常系）
  test("project_index_failed_alert", async ({ page }) => {
    // 準備
    const reason = `git archive --format=tar ${"0123456789abcdef".repeat(5)}: 20 秒を超えたため止めました`;
    await page.setViewportSize({ width: 390, height: 844 });
    await mockApi(page, {
      document: () =>
        problem(502, {
          detail: `project-index（http://127.0.0.1:8786）が要求を処理できませんでした。${reason}`,
          projectIndex: { address: "http://127.0.0.1:8786", reason, kind: "failed" },
        }),
    });
    // 実行
    await page.goto("/sample/docs/doc-1");
    // 検証
    const alert = page.getByRole("alert").filter({ hasText: "project-index が要求を処理できませんでした" });
    await expect(alert).toContainText(
      "時間をおいて再読み込みすると、開けることがあります。続くときは、project-index のログで原因を確認してください。",
    );
    await expect(alert.locator("dd")).toHaveText(["http://127.0.0.1:8786", reason]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    ).toBe(true);
  });
});

test.describe("編集中のボタン", () => {
  // トップバーの編集中のボタンで、この画面の編集中のパネルを開閉する（正常系）
  test("open_pending_panel", async ({ page }) => {
    await openDoc(page);
    const button = page.getByRole("button", { name: /^編集中 \d+ 件$/ });
    await button.click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-1$/);
    const panel = page.getByRole("dialog", { name: "編集中" }).or(page.getByRole("complementary", { name: "編集中" }));
    await expect(panel).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
  });
});

test.describe("検索から除外のマーカー", () => {
  const withExcluded: Handler = ({ path }) => ({
    body: documentResponse({
      path,
      tabs: [
        {
          title: "規約",
          active: true,
          items: [
            { kind: "page", title: "文書 1", path: "docs/doc-1", items: [], change: null, excluded: false },
            { kind: "page", title: "文書 2", path: "docs/doc-2", items: [], change: null, excluded: true },
          ],
        },
      ],
    }),
  });

  // 検索から除外される page をサイドバーに残し、`検索から除外` のアイコンを付け、選ぶとその文書を開く（正常系）
  test("sidebar_excluded_marker", async ({ page }) => {
    await openDoc(page, "/sample/docs/doc-1", { document: withExcluded });
    const list = page.getByRole("navigation", { name: "文書の一覧" });
    const excluded = list.getByRole("link", { name: /文書 2/ });
    await expect(list.getByRole("img", { name: "検索から除外" })).toHaveCount(1);
    await expect(excluded.getByRole("img", { name: "検索から除外" })).toBeVisible();
    await expect(list.getByRole("link", { name: "文書 1" }).getByRole("img")).toHaveCount(0);
    await excluded.click();
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2$/);
  });
});

const RULE_SOURCE = [
  "id: rule-sample",
  "name: 文書の編集",
  "description: 本文を編集する決まり",
  "status: current",
  "items:",
  "  - id: overview",
  "    body: 本文の概要",
  "rows:",
  "  - word: 直す",
  "    replacement: 修正",
  "",
].join("\n");

const RULE_ROWS = [{ word: "直す", replacement: "修正" }];

/** 規約の文書（YAML）の本文の編集の情報 */
const ruleEdit = (): DocumentEdit => ({
  docId: "rule-sample",
  kind: "rule",
  filePath: "docs/rule/rule-sample.yaml",
  version: "a1b2c3",
  baseCommit: "1111111",
  language: "yaml",
  source: RULE_SOURCE,
  blocks: [
    { path: "description", label: "説明", type: "string", value: "本文を編集する決まり", markdown: "本文を編集する決まり", options: null, columns: null },
    { path: "status", label: "状態", type: "enum", value: "current", markdown: "**状態**: current", options: ["current", "draft"], columns: null },
    { path: "#items[overview].body", label: "overview の 本文", type: "markdown", value: "本文の概要", markdown: "### overview\n\n本文の概要", options: null, columns: null },
    {
      path: "rows",
      label: "単語の対応表",
      type: "table",
      value: RULE_ROWS,
      markdown: "| word | replacement |\n| --- | --- |\n| 直す | 修正 |",
      options: null,
      columns: ["word", "replacement"],
    },
  ],
  titleBlock: { path: "name", label: "名前", type: "string", value: "文書の編集", markdown: "# 文書の編集", options: null, columns: null },
});

/** ガイドの文書（Markdown）の本文の編集の情報 */
const guideEdit = (): DocumentEdit => ({
  docId: "guide.md",
  kind: "guide",
  filePath: "guide.md",
  version: "d4e5f6",
  baseCommit: "1111111",
  language: "markdown",
  source: "# 案内\n\n1 行目の説明\n",
  blocks: [],
  titleBlock: null,
});

const RULE_PATH = "docs/rule/rule-sample";
const RULE_URL = `/sample/${RULE_PATH}`;
const GUIDE_URL = "/sample/files/guide.md";

type EditEnv = {
  previews: { path: string; content: string }[];
  commits: Record<string, unknown>[];
  documents: () => number;
};

/** 本文を編集できる文書を返却し、本文のプレビューと直コミットを差し替えて画面を開く */
const openEditable = async (
  page: Page,
  url: string,
  options: {
    edit?: DocumentEdit | null;
    preview?: (content: string) => Record<string, unknown>;
  } = {},
): Promise<EditEnv> => {
  let documents = 0;
  const document: Handler = ({ path, query }) => {
    documents += 1;
    const guide = path.startsWith("files/");
    const edit = options.edit !== undefined ? options.edit : guide ? guideEdit() : ruleEdit();
    return {
      body: documentResponse({
        path,
        ref: query.get("ref") ?? "develop",
        markdown: guide ? "# 案内\n\n1 行目の説明\n" : "# 文書の編集\n\n本文を編集する決まり\n\n**状態**: current\n",
        edit,
      }),
    };
  };
  await mockApi(page, { document });
  const env: EditEnv = { previews: [], commits: [], documents: () => documents };
  await page.route("**/_api/sources/sample/preview", async (route) => {
    const body = route.request().postDataJSON() as { path: string; content: string };
    env.previews.push(body);
    const reply = options.preview?.(body.content) ?? { markdown: `プレビュー: ${body.content.length}`, conversionError: null, fallback: false };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(reply) });
  });
  await page.route("**/_api/sources/sample/commits", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    env.commits.push(body);
    const edits = (body.edits as { key: string }[]) ?? [];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        applied: body.dryRun !== true,
        results: edits.map((item) => ({ key: item.key, status: "updated", version: "v2", diff: `+${item.key}` })),
        commit: body.dryRun === true ? null : { sha: "0a1b2c3d4e5f", branch: "develop", retried: false },
      }),
    });
  });
  await page.goto(url);
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  return env;
};

const pendingButton = (page: Page, count: number) => page.getByRole("button", { name: `編集中 ${count} 件` });

/** 表示した場所で修正の表示で、文字列の項目を修正する */
const editInline = async (page: Page, label: string, value: string) => {
  await page.getByRole("button", { name: `${label} を編集` }).click();
  const input = page.getByRole("textbox", { name: label, exact: true });
  await input.fill(value);
  await input.press("Enter");
};

test.describe("編集のボタン", () => {
  // edit がある YAML の文書は、編集のボタンで `edit=fields` を開く（正常系）
  test("edit_button_yaml", async ({ page }) => {
    await openEditable(page, RULE_URL);
    await page.getByRole("button", { name: "編集", exact: true }).click();
    await expect(page).toHaveURL(/edit=fields/);
    await expect(page.getByRole("button", { name: "説明 を編集" })).toBeVisible();
  });

  // Markdown の文書は、編集のボタンで `edit=file` を開く（正常系）
  test("edit_button_markdown", async ({ page }) => {
    await openEditable(page, GUIDE_URL);
    await page.getByRole("button", { name: "編集", exact: true }).click();
    await expect(page).toHaveURL(/edit=file/);
    await expect(page.getByRole("textbox", { name: "guide.md" })).toBeVisible();
  });

  // edit が null の文書には、編集のボタンを出さない（正常系）
  test("edit_button_hidden", async ({ page }) => {
    await openEditable(page, RULE_URL, { edit: null });
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "編集", exact: true })).toHaveCount(0);
  });
});

test.describe("編集の方式の切り替え", () => {
  // YAML の文書は 2 つの方式を出し、今の方式を押した状態にして、押すと方式を切り替える（正常系）
  test("edit_mode_toggle", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    const group = page.getByRole("group", { name: "編集の方式" });
    await expect(group.getByRole("button", { name: "表示した場所で修正" })).toHaveAttribute("aria-pressed", "true");
    await expect(group.getByRole("button", { name: "ファイル全体" })).toHaveAttribute("aria-pressed", "false");
    await group.getByRole("button", { name: "ファイル全体" }).click();
    await expect(page).toHaveURL(/edit=file/);
    await expect(page.getByRole("textbox", { name: "docs/rule/rule-sample.yaml" })).toBeVisible();
  });

  // もう一方の方式の変更がある間は切り替えさせず、理由を出す（正常系）
  test("edit_mode_toggle_disabled", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    await editInline(page, "説明", "修正後の説明");
    const group = page.getByRole("group", { name: "編集の方式" });
    await expect(group.getByRole("button", { name: "ファイル全体" })).toBeDisabled();
    await expect(page.getByText("表示した場所で修正の変更をコミットするか元に戻すと切り替えられます。")).toBeVisible();
  });

  // Markdown の文書には方式の切り替えを出さない（正常系）
  test("edit_mode_toggle_markdown", async ({ page }) => {
    await openEditable(page, `${GUIDE_URL}?edit=file`);
    await expect(page.getByRole("group", { name: "編集の方式" })).toHaveCount(0);
  });
});

test.describe("編集を終了", () => {
  // 編集を終了で edit を除いた同じ文書を開き、編集中の変更は残す（正常系）
  test("edit_finish", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    await editInline(page, "説明", "修正後の説明");
    await page.getByRole("button", { name: "編集を終了" }).click();
    await expect(page).not.toHaveURL(/edit=/);
    await expect(page.getByRole("button", { name: "編集", exact: true })).toBeVisible();
    await expect(pendingButton(page, 1)).toBeVisible();
  });
});

test.describe("項目のブロックとその場の入力欄", () => {
  // 修正できる項目ごとに編集のボタンを並べ、文字列の項目はその場の入力欄で修正して変更ありを出す（正常系）
  test("inline_string", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    for (const label of ["説明", "状態", "overview の 本文", "単語の対応表", "名前"]) {
      await expect(page.getByRole("button", { name: `${label} を編集` })).toBeVisible();
    }
    await page.getByRole("button", { name: "説明 を編集" }).click();
    const input = page.getByRole("textbox", { name: "説明", exact: true });
    await expect(input).toBeFocused();
    await expect(input).toHaveValue("本文を編集する決まり");
    await input.fill("修正後の説明");
    await input.press("Enter");
    await expect(input).toHaveCount(0);
    await expect(page.locator('[data-edit-path="description"]')).toContainText("変更あり");
    await expect(pendingButton(page, 1)).toBeVisible();
  });

  // 元の値に戻すと編集中の変更から除く（正常系）
  test("inline_revert", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    await editInline(page, "説明", "修正後の説明");
    await expect(pendingButton(page, 1)).toBeVisible();
    await editInline(page, "説明", "本文を編集する決まり");
    await expect(pendingButton(page, 0)).toBeVisible();
  });

  // enum の項目は選択肢から選ぶ（正常系）
  test("inline_enum", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    await page.getByRole("button", { name: "状態 を編集" }).click();
    await page.getByRole("combobox", { name: "状態" }).click();
    await page.getByRole("option", { name: "draft" }).click();
    await expect(pendingButton(page, 1)).toBeVisible();
  });

  // 文書のタイトルもその場の入力欄で修正する（正常系）
  test("inline_title", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    await editInline(page, "名前", "修正後の名前");
    await expect(page.getByRole("heading", { level: 1, name: "修正後の名前" })).toBeVisible();
    await expect(pendingButton(page, 1)).toBeVisible();
  });
});

test.describe("表のセルの入力欄", () => {
  // 表の項目は行と列ごとの入力欄で修正し、行の配列を編集中の変更に入れる（正常系）
  test("table_cells", async ({ page }) => {
    const env = await openEditable(page, `${RULE_URL}?edit=fields`);
    await page.getByRole("button", { name: "単語の対応表 を編集" }).click();
    const cell = page.getByRole("textbox", { name: "単語の対応表 の 1 行目の replacement" });
    await expect(cell).toHaveValue("修正");
    await cell.fill("修正する");
    await expect(pendingButton(page, 1)).toBeVisible();
    await pendingButton(page, 1).click();
    await page.getByRole("button", { name: "差分確認" }).click();
    await expect.poll(() => env.commits.length).toBe(1);
    expect(env.commits[0]).toMatchObject({
      edits: [{ kind: "body", docId: "rule-sample", values: { rows: [{ word: "直す", replacement: "修正する" }] } }],
    });
  });
});

test.describe("Markdown の項目のパネル", () => {
  // Markdown の項目はパネルのエディタで修正し、プレビューを出し、元に戻すで取り消して、Esc で閉じる（正常系）
  test("markdown_field_panel", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    const open = page.getByRole("button", { name: "overview の 本文 を編集" });
    await open.click();
    const sheet = page.getByRole("dialog", { name: "overview の 本文 の編集" });
    await expect(sheet).toContainText("#items[overview].body");
    const editor = sheet.getByRole("textbox", { name: "本文" });
    await expect(editor).toHaveValue("本文の概要");
    await editor.fill("修正後の概要");
    await expect(sheet.getByRole("region", { name: "プレビュー" })).toContainText("修正後の概要");
    await expect(sheet.getByText("変更あり")).toBeVisible();
    await expect(pendingButton(page, 1)).toBeVisible();
    await sheet.getByRole("button", { name: "元に戻す" }).click();
    await expect(editor).toHaveValue("本文の概要");
    await expect(pendingButton(page, 0)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);
    await expect(open).toBeFocused();
  });
});

test.describe("ファイル全体のエディタとプレビュー", () => {
  // YAML の文書は、入力が止まった後に本文のプレビューを呼んで描き、変更ありと元に戻すを出す（正常系）
  test("whole_file_yaml", async ({ page }) => {
    const env = await openEditable(page, `${RULE_URL}?edit=file`, {
      preview: (content) => ({ markdown: content.includes("修正後") ? "修正後の説明を描いた" : "元の説明", conversionError: null, fallback: false }),
    });
    const editor = page.getByRole("textbox", { name: "docs/rule/rule-sample.yaml" });
    await expect(editor).toHaveValue(RULE_SOURCE);
    await editor.fill(RULE_SOURCE.replace("本文を編集する決まり", "修正後の説明"));
    await expect(page.getByRole("region", { name: "プレビュー" })).toContainText("修正後の説明を描いた");
    expect(env.previews.at(-1)).toMatchObject({ path: RULE_PATH });
    await expect(page.getByText("変更あり")).toBeVisible();
    await page.getByRole("button", { name: "元に戻す" }).click();
    await expect(editor).toHaveValue(RULE_SOURCE);
    await expect(pendingButton(page, 0)).toBeVisible();
  });

  // 解析できない YAML は、行と列と理由の alert を出し、エディタに aria-invalid を付け、最後に変換できた内容を残す（異常系）
  test("whole_file_invalid", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=file`, {
      preview: (content) =>
        content.includes("\t")
          ? { markdown: null, conversionError: { line: 3, column: 1, detail: "タブは使用できません" }, fallback: false }
          : { markdown: "元の説明", conversionError: null, fallback: false },
    });
    const editor = page.getByRole("textbox", { name: "docs/rule/rule-sample.yaml" });
    await editor.fill(RULE_SOURCE.replace("description:", "\tdescription:"));
    const alert = page.getByRole("alert").filter({ hasText: "YAML として解析できません" });
    await expect(alert).toContainText("3 行 1 列: タブは使用できません。このままでは差分確認とコミットでエラーが発生します。");
    await expect(editor).toHaveAttribute("aria-invalid", "true");
  });

  // 変換のスクリプトを指す種類は、標準の変換で表示している旨を出す（正常系）
  test("whole_file_fallback", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=file`, {
      preview: () => ({ markdown: "標準の変換", conversionError: null, fallback: true }),
    });
    await page.getByRole("textbox", { name: "docs/rule/rule-sample.yaml" }).fill(`${RULE_SOURCE}# 追記\n`);
    await expect(page.getByText("この種類のプレビューは、配信元の変換を使用できないため標準の変換で表示しています。")).toBeVisible();
  });

  // Markdown の文書は、本文のプレビューを呼ばずにエディタの値をそのまま描く（正常系）
  test("whole_file_markdown", async ({ page }) => {
    const env = await openEditable(page, `${GUIDE_URL}?edit=file`);
    const editor = page.getByRole("textbox", { name: "guide.md" });
    await editor.fill("# 案内\n\n修正後の説明\n");
    await expect(page.getByRole("region", { name: "プレビュー" })).toContainText("修正後の説明");
    expect(env.previews).toEqual([]);
  });
});

test.describe("編集中のパネル（文書の画面）", () => {
  // トップバーの編集中のボタンでこの画面の編集中のパネルを開閉し、本文の変更の行で文書を編集の表示で開く（正常系）
  test("pending_panel_on_doc_view", async ({ page }) => {
    await openEditable(page, `${RULE_URL}?edit=fields`);
    await editInline(page, "説明", "修正後の説明");
    await page.getByRole("button", { name: "編集を終了" }).click();
    await pendingButton(page, 1).click();
    const panel = page.getByRole("dialog", { name: "編集中" }).or(page.getByRole("complementary", { name: "編集中" }));
    await expect(panel).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`${RULE_URL}$`));
    await panel.getByRole("button", { name: "説明（docs/rule/rule-sample.yaml） の行へ移動" }).click();
    await expect(page).toHaveURL(/edit=fields/);
    await expect(panel).toBeVisible();
  });

  // コミットした後は文書を再取得する（正常系）
  test("refetch_after_commit", async ({ page }) => {
    const env = await openEditable(page, `${RULE_URL}?edit=fields`);
    await editInline(page, "説明", "修正後の説明");
    await pendingButton(page, 1).click();
    const before = env.documents();
    await page.getByRole("button", { name: "コミット" }).click();
    const dialog = page.getByRole("dialog", { name: "コミットしますか？" });
    await dialog.getByRole("textbox", { name: "コミットの説明" }).fill("説明を修正する");
    await dialog.getByRole("button", { name: "コミット" }).click();
    await expect(page.getByText("develop にコミットしました（0a1b2c3）")).toBeVisible();
    expect(env.commits.at(-1)).toMatchObject({
      baseCommit: "1111111",
      edits: [{ kind: "body", docId: "rule-sample", docKind: "rule", expectedVersion: "a1b2c3", docPath: "docs/rule/rule-sample.yaml", values: { description: "修正後の説明" } }],
    });
    await expect.poll(env.documents).toBeGreaterThan(before);
  });
});

test.describe("本文のスクロール", () => {
  /** 画面より長い本文 */
  const LONG_BODY = `# 文書 1\n\n${Array.from(
    { length: 30 },
    (_, index) => `## 節 ${index + 1}\n\n${"本文の段落です。".repeat(40)}\n`,
  ).join("\n")}`;

  // 画面を表示領域の高さに収め、本文を末尾までスクロールしても画面全体の縦のスクロールバーを出さない（正常系）
  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    test(`body_scroll_without_page_scrollbar_${viewport.width}`, async ({
      page,
    }) => {
      // 準備
      await page.setViewportSize(viewport);
      await openDoc(page, "/sample/docs/doc-1", {
        document: ({ path }) => ({
          body: documentResponse({ path, markdown: LONG_BODY }),
        }),
      });
      const scroll = page.locator("#doc-scroll");
      await expect(
        page.getByRole("heading", { level: 2, name: /^節 1 / }),
      ).toBeVisible();
      // 実行
      await scroll.evaluate((element) =>
        element.scrollTo(0, element.scrollHeight),
      );
      // 検証
      await expect
        .poll(() => scroll.evaluate((element) => element.scrollTop))
        .toBeGreaterThan(0);
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollHeight <=
            document.documentElement.clientHeight,
        ),
      ).toBe(true);
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      await expect(
        page.getByRole("navigation", { name: "文書の種類" }),
      ).toBeInViewport();
    });
  }
});

test.describe("文書の一覧の長い名前", () => {
  const LONG_GROUP = "設計書のまとまりの名前が長いときの見出し".repeat(3);
  const LONG_PAGE = "文書の名前が長いときにサイドバーの幅を超える文書".repeat(
    3,
  );
  const LONG_TABS = [
    {
      title: "規約",
      active: true,
      items: [
        {
          kind: "group" as const,
          title: LONG_GROUP,
          path: null,
          change: null,
          items: [
            {
              kind: "page" as const,
              title: LONG_PAGE,
              path: "docs/doc-1",
              items: [],
              change: null,
            },
          ],
        },
      ],
    },
  ];

  // page の名前と group の見出しを 1 行で出し、収まらない末尾を省略して title に全文を持たせる（正常系）
  test("sidebar_long_names_truncated", async ({ page }) => {
    // 準備・実行
    await openDoc(page, "/sample/docs/doc-1", {
      document: ({ path }) => ({
        body: documentResponse({ path, tabs: LONG_TABS }),
      }),
    });
    const sidebar = page.getByRole("navigation", { name: "文書の一覧" });
    const groupName = sidebar.getByTitle(LONG_GROUP);
    const pageName = sidebar.getByTitle(LONG_PAGE);
    // 検証
    for (const name of [groupName, pageName]) {
      await expect(name).toBeVisible();
      const style = await name.evaluate((element) => {
        const computed = getComputedStyle(element);
        return {
          whiteSpace: computed.whiteSpace,
          textOverflow: computed.textOverflow,
          clipped: element.scrollWidth > element.clientWidth,
        };
      });
      expect(style).toEqual({
        whiteSpace: "nowrap",
        textOverflow: "ellipsis",
        clipped: true,
      });
    }
    const nav = await boxOf(sidebar);
    expect(
      (await boxOf(pageName)).x + (await boxOf(pageName)).width,
    ).toBeLessThanOrEqual(nav.x + nav.width + 1);
  });
});

test.describe("差分の案内の文字色", () => {
  // 「比較元」「比較先」のラベルが案内の背景とのコントラスト 4.5:1 以上になる（正常系）
  test("diff_banner_label_contrast", async ({ page }) => {
    // 準備・実行
    await openDoc(page, "/sample/docs/doc-1?base=7c0aa11", {
      document: withDiff,
    });
    const banner = page.getByRole("region", { name: "差分" });
    await expect(banner).toBeVisible();
    // 検証
    const result = await new AxeBuilder({ page })
      .include('[aria-label="差分"]')
      .withRules(["color-contrast"])
      .analyze();
    expect(result.violations).toEqual([]);
  });
});
