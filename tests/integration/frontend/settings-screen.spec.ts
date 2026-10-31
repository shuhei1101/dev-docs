import { type Page, expect, test } from "@playwright/test";

import { mockApi, problem } from "./support/api-mock";
import type { Handler } from "./support/api-mock";
import {
  documentResponse,
  settingsSource,
  settingsView,
} from "./support/fixtures";

const TOAST = "端末の設定を保存し、配信元を読み直しました。";

const open = async (
  page: Page,
  overrides: Parameters<typeof mockApi>[1] = {},
) => {
  const api = await mockApi(page, overrides);
  await page.goto("/_settings");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("設定");
  await expect(
    page.getByRole("table").or(page.getByText("配信元はありません。")),
  ).toBeVisible();
  return api;
};

const withSources =
  (...rows: ReturnType<typeof settingsSource>[]): Handler =>
  () => ({ body: settingsView(rows) });

const dialog = (page: Page) => page.getByRole("dialog");

const openAdd = async (page: Page) => {
  await page.getByRole("button", { name: "配信元を追加" }).click();
  await expect(dialog(page)).toBeVisible();
};

const openEdit = async (page: Page, id: string) => {
  await page.getByRole("button", { name: `${id} を編集` }).click();
  await expect(dialog(page)).toBeVisible();
};

const fillValid = async (page: Page, id = "extra") => {
  await page.getByLabel("配信元の ID").fill(id);
  await page.getByLabel("設定ファイル").fill("/home/me/extra/dev-docs.yaml");
  await page.getByLabel("読み取りの範囲").fill("/home/me/**");
};

test.describe("ページのタイトル", () => {
  // 設定画面のタイトルを `設定 | dev-docs` にする（正常系）
  test("page_title", async ({ page }) => {
    await open(page);
    await expect(page).toHaveTitle("設定 | dev-docs");
  });
});

test.describe("本文へスキップ", () => {
  // キーボードでフォーカスしたときに見え、クリックで本文へフォーカスを移す（正常系）
  test("skip_link", async ({ page }) => {
    // 準備
    await open(page);
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
  // 画面名のクリックで配信中の配信元の先頭のトップを開く（正常系）
  test("topbar_home_link", async ({ page }) => {
    await open(page);
    await page.getByRole("banner").getByRole("link", { name: "dev-docs" }).click();
    await expect(page).toHaveURL(/\/sample$/);
  });

  // 明暗のボタンで明暗を切り替え、ブラウザに保存する（正常系）
  test("topbar_color_scheme_toggle", async ({ page }) => {
    // 準備
    await open(page);
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

  // 画面名と明暗のボタンだけを出す（正常系）
  test("topbar_only_title_and_color_scheme", async ({ page }) => {
    await open(page);
    const bar = page.getByRole("banner");
    await expect(bar.getByRole("button")).toHaveCount(1);
    await expect(bar.getByText("設定", { exact: true })).toBeVisible();
  });
});

test.describe("文書の画面に戻る", () => {
  // 直前に開いていた文書の画面へ戻る（正常系）
  test("back_link_to_previous_doc", async ({ page }) => {
    // 準備
    await mockApi(page, {
      document: ({ path }) => ({ body: documentResponse({ path }) }),
    });
    await page.goto("/sample/docs/doc-2?rev=develop");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByLabel("設定", { exact: true }).click();
    // 実行
    await page.getByRole("link", { name: "文書の画面に戻る" }).click();
    // 検証
    await expect(page).toHaveURL(/\/sample\/docs\/doc-2\?rev=develop$/);
  });

  // 直前の文書が無ければ配信中の配信元の先頭のトップを開く（正常系）
  test("back_link_without_previous_doc", async ({ page }) => {
    await open(page);
    await page.getByRole("link", { name: "文書の画面に戻る" }).click();
    await expect(page).toHaveURL(/\/sample$/);
  });

  // 配信中の配信元が無いときは出さない（正常系）
  test("back_link_when_none_serving", async ({ page }) => {
    await open(page, { settings: () => ({ body: settingsView([]) }) });
    await expect(page.getByRole("link", { name: "文書の画面に戻る" })).toHaveCount(0);
  });
});

test.describe("見出し", () => {
  // 画面の見出し 1 に `設定` を出す（正常系）
  test("heading", async ({ page }) => {
    await open(page);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("設定");
  });

  // 配信元のセクションの見出しに `配信元` を出す（正常系）
  test("sources_heading", async ({ page }) => {
    await open(page);
    await expect(page.getByRole("heading", { level: 2, name: "配信元" })).toBeVisible();
  });

  // キーボードのセクションの見出しに `キーボード` を出す（正常系）
  test("keyboard_heading", async ({ page }) => {
    await open(page);
    await expect(page.getByRole("heading", { level: 2, name: "キーボード" })).toBeVisible();
  });
});

test.describe("配信元の読み込み中の表示", () => {
  // 端末の設定の取得が 1 秒を超えたときだけ、表の行の形の枠を出す（正常系）
  test("loading_skeleton", async ({ page }) => {
    // 準備
    await mockApi(page, {
      settings: () => ({ body: settingsView(), delayMs: 2500 }),
    });
    // 実行
    await page.goto("/_settings");
    // 検証
    const skeleton = page.locator('[aria-busy="true"]');
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("設定");
    await expect(skeleton).toHaveCount(0);
    await expect(skeleton).toBeVisible({ timeout: 2000 });
    await expect(page.getByRole("table")).toBeVisible();
    await expect(skeleton).toHaveCount(0);
  });
});

test.describe("配信元が無いことの表示", () => {
  // 配信元が 0 件のとき `配信元はありません。` を出し、表を出さない（正常系）
  test("empty_message", async ({ page }) => {
    await open(page, { settings: () => ({ body: settingsView([]) }) });
    await expect(page.getByText("配信元はありません。")).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
  });
});

test.describe("配信元の一覧", () => {
  // 列を `配信元`・`設定ファイル`・`状態`・`操作` の順に出し、端末の設定の並び順で行を並べる（正常系）
  test("table_columns_and_order", async ({ page }) => {
    // 準備・実行
    await open(page, {
      settings: withSources(settingsSource("zeta"), settingsSource("alpha")),
    });
    // 検証
    const headers = page.getByRole("columnheader");
    await expect(headers).toHaveText(["配信元", "設定ファイル", "状態", "操作"]);
    const rows = page.getByRole("row");
    await expect(rows.nth(1)).toContainText("zeta");
    await expect(rows.nth(2)).toContainText("alpha");
  });
});

test.describe("配信元の ID", () => {
  // 配信中の行だけ ID をリンクにし、クリックでその配信元のトップを開く（正常系）
  test("id_link_when_serving", async ({ page }) => {
    // 準備
    await open(page);
    // 実行
    await page.getByRole("table").getByRole("link", { name: "knowledge" }).click();
    // 検証
    await expect(page).toHaveURL(/\/knowledge$/);
  });

  // 配信していない行の ID はリンクにしない（正常系）
  test("id_not_link_when_not_serving", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("broken", { status: "not_served" })),
    });
    await expect(page.getByRole("table").getByRole("link")).toHaveCount(0);
    await expect(page.locator("span.font-mono", { hasText: "broken" })).toBeVisible();
  });
});

test.describe("設定ファイル", () => {
  // 設定ファイルのパスを 1 行に 1 つ、等幅で出す（正常系）
  test("config_paths", async ({ page }) => {
    await open(page, {
      settings: withSources(
        settingsSource("sample", {
          config: ["/home/me/a/dev-docs.yaml", "/home/me/b/dev-docs.local.yaml"],
        }),
      ),
    });
    const first = page.getByText("/home/me/a/dev-docs.yaml");
    const second = page.getByText("/home/me/b/dev-docs.local.yaml");
    await expect(first).toHaveClass(/font-mono/);
    await expect(second).toHaveClass(/font-mono/);
  });
});

test.describe("状態", () => {
  // 配信中をアイコンと `配信中` で出す（正常系）
  test("status_serving", async ({ page }) => {
    await open(page, { settings: withSources(settingsSource("a")) });
    await expect(page.getByText("配信中", { exact: true })).toBeVisible();
  });

  // 配信していない行を `配信していない` で出す（正常系）
  test("status_not_served", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("a", { status: "not_served" })),
    });
    await expect(page.getByText("配信していない", { exact: true })).toBeVisible();
  });

  // 無効の行を `無効` で出す（正常系）
  test("status_disabled", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("a", { status: "disabled", enabled: false })),
    });
    await expect(page.getByText("無効", { exact: true })).toBeVisible();
  });

  // 読み直していない行を `読み直していない` で出す（正常系）
  test("status_pending_reload", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("fresh", { id: null, status: "pending_reload" })),
    });
    await expect(page.getByText("読み直していない", { exact: true })).toBeVisible();
  });
});

test.describe("状態の補足", () => {
  // 配信していないとき、外した旨と errors[] ごとの `{path} {reason}` を出す（正常系）
  test("status_note_when_not_served", async ({ page }) => {
    await open(page, {
      settings: withSources(
        settingsSource("a", {
          status: "not_served",
          errors: [{ path: "documents[0].paths", reason: "必須のキーがありません" }],
        }),
      ),
    });
    await expect(page.getByText("起動時の検証で外しました。")).toBeVisible();
    await expect(page.getByText("documents[0].paths 必須のキーがありません")).toBeVisible();
  });

  // 設定のバージョンが古いとき、設定とサーバーのバージョンを出す（正常系）
  test("status_note_when_config_version_old", async ({ page }) => {
    await open(page, {
      settings: withSources(
        settingsSource("a", { configVersion: { config: "0", server: "3" } }),
      ),
    });
    await expect(page.getByText("設定のバージョン 0（サーバーが読めるのは 3）")).toBeVisible();
  });

  // 無効のとき `enabled が false です` を出す（正常系）
  test("status_note_when_disabled", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("a", { status: "disabled", enabled: false })),
    });
    await expect(page.getByText("enabled が false です")).toBeVisible();
  });

  // 読み直していないとき、ファイルにあるが読み直していない旨を出す（正常系）
  test("status_note_when_pending_reload", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("a", { status: "pending_reload" })),
    });
    await expect(page.getByText("ファイルにありますが、まだ読み直していません。")).toBeVisible();
  });

  // 配信中で設定のバージョンも古くないとき補足を出さない（正常系）
  test("status_note_when_serving", async ({ page }) => {
    await open(page, { settings: withSources(settingsSource("a")) });
    await expect(page.getByText("起動時の検証で外しました。")).toHaveCount(0);
    await expect(page.getByText("enabled が false です")).toHaveCount(0);
  });
});

test.describe("配信元を追加", () => {
  // クリックで追加のダイアログを開く（正常系）
  test("add_button", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await expect(dialog(page).getByRole("heading", { name: "配信元を追加" })).toBeVisible();
  });
});

test.describe("編集ボタン", () => {
  // クリックでその行の値を入れたダイアログを編集で開く（正常系）
  test("edit_button", async ({ page }) => {
    // 準備
    await open(page, {
      settings: withSources(
        settingsSource("sample", {
          scope: { read: ["/home/me/**"], write: ["/home/me/sample/**"] },
        }),
      ),
    });
    // 実行
    await openEdit(page, "sample");
    // 検証
    await expect(dialog(page).getByRole("heading", { name: "配信元を編集" })).toBeVisible();
    await expect(page.getByLabel("設定ファイル")).toHaveValue("/home/me/sample/dev-docs.yaml");
    await expect(page.getByLabel("読み取りの範囲")).toHaveValue("/home/me/**");
    await expect(page.getByLabel("書き込みの範囲")).toHaveValue("/home/me/sample/**");
  });
});

test.describe("削除ボタン", () => {
  // クリックで削除の確認のダイアログを開く（正常系）
  test("delete_button", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "sample を削除" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
  });
});

test.describe("1 文字のショートカットのスイッチ", () => {
  // 初期値をオンにし、補助文を出す（正常系）
  test("single_key_switch_initial", async ({ page }) => {
    await open(page);
    await expect(page.getByRole("switch", { name: "1 文字のショートカットを使う" })).toBeChecked();
    await expect(
      page.getByText("この端末のブラウザに保存します。"),
    ).toBeVisible();
  });

  // 切り替えでブラウザの localStorage に保存し、`?` を受けなくする（正常系）
  test("single_key_switch_toggle", async ({ page }) => {
    // 準備
    await open(page);
    const toggle = page.getByRole("switch", { name: "1 文字のショートカットを使う" });
    // 実行
    await toggle.click();
    await page.getByRole("heading", { level: 1 }).click();
    await page.keyboard.press("Shift+/");
    // 検証
    await expect(toggle).not.toBeChecked();
    const stored = await page.evaluate(() =>
      localStorage.getItem("dev-docs:preferences"),
    );
    expect(stored).toContain('"singleKeyShortcuts":false');
    await expect(page.getByRole("dialog", { name: "キーボードのショートカット" })).toHaveCount(0);
  });
});

test.describe("ショートカットの一覧", () => {
  // `ショートカットの一覧を開く` で設定画面のキーを出す（正常系）
  test("shortcut_open_button", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "ショートカットの一覧を開く" }).click();
    await expect(page.getByRole("dialog", { name: "キーボードのショートカット" })).toBeVisible();
  });

  // `?` を押すと設定画面のキーを出す（正常系）
  test("shortcut_key", async ({ page }) => {
    await open(page);
    await page.keyboard.press("Shift+/");
    await expect(page.getByRole("dialog", { name: "キーボードのショートカット" })).toBeVisible();
  });
});

test.describe("配信元のダイアログのタイトル", () => {
  // 追加は `配信元を追加` を出す（正常系）
  test("dialog_title_when_add", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await expect(dialog(page).getByRole("heading", { name: "配信元を追加" })).toBeVisible();
  });

  // 編集は `配信元を編集` とその下に `配信元 {id}` を出す（正常系）
  test("dialog_title_when_edit", async ({ page }) => {
    await open(page);
    await openEdit(page, "sample");
    await expect(dialog(page).getByRole("heading", { name: "配信元を編集" })).toBeVisible();
    await expect(dialog(page).getByText("配信元 sample", { exact: true })).toBeVisible();
  });
});

test.describe("配信元の ID の入力欄", () => {
  // 追加のとき、必須の表示・補助文・オフの入力の目的・初期フォーカスで出す（正常系）
  test("id_input_when_add", async ({ page }) => {
    // 準備・実行
    await open(page);
    await openAdd(page);
    // 検証
    const input = page.getByLabel("配信元の ID");
    await expect(input).toHaveValue("");
    await expect(input).toBeFocused();
    await expect(input).toHaveAttribute("autocomplete", "off");
    await expect(dialog(page).getByText("必須").first()).toBeVisible();
    await expect(
      dialog(page).getByText("画面の URL と文書の MCP の source に使います。英小文字・数字・ハイフンで入力します。"),
    ).toBeVisible();
  });

  // 編集のとき入力欄を出さない（正常系）
  test("id_input_when_edit", async ({ page }) => {
    await open(page);
    await openEdit(page, "sample");
    await expect(page.getByLabel("配信元の ID")).toHaveCount(0);
  });

  // 入力した値を変換しない（正常系）
  test("id_input_keeps_value", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await page.getByLabel("配信元の ID").fill("Sample_1");
    await expect(page.getByLabel("配信元の ID")).toHaveValue("Sample_1");
  });
});

test.describe("設定ファイルの入力欄", () => {
  // プレースホルダ・必須の表示・補助文を出し、追加は空にする（正常系）
  test("config_input_when_add", async ({ page }) => {
    await open(page);
    await openAdd(page);
    const input = page.getByLabel("設定ファイル");
    await expect(input).toHaveValue("");
    await expect(input).toHaveAttribute("placeholder", "~/repo/sample-docs/dev-docs.yaml");
    await expect(
      dialog(page).getByText("1 行に 1 つ。後のファイルが前のファイルの同じキーを上書きします。"),
    ).toBeVisible();
  });

  // 編集は行の config を 1 行に 1 つ入れ、初期フォーカスを置く（正常系）
  test("config_input_when_edit", async ({ page }) => {
    // 準備
    await open(page, {
      settings: withSources(
        settingsSource("sample", { config: ["/home/me/a.yaml", "/home/me/b.yaml"] }),
      ),
    });
    // 実行
    await openEdit(page, "sample");
    // 検証
    const input = page.getByLabel("設定ファイル");
    await expect(input).toHaveValue("/home/me/a.yaml\n/home/me/b.yaml");
    await expect(input).toBeFocused();
  });
});

test.describe("配信のスイッチ", () => {
  // 項目の見出しに `配信` を出し、スイッチの横に `配信する` を出す（正常系）
  test("enabled_switch_heading", async ({ page }) => {
    await open(page);
    await openAdd(page);
    const group = dialog(page).getByRole("group", { name: "配信", exact: true });
    await expect(group).toBeVisible();
    await expect(group.getByRole("switch", { name: "配信する" })).toBeVisible();
  });

  // 追加はオンで、補助文を出す（正常系）
  test("enabled_switch_when_add", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await expect(dialog(page).getByRole("switch", { name: "配信する" })).toBeChecked();
    await expect(
      dialog(page).getByText("外すと、設定を残したまま配信を止めます。"),
    ).toBeVisible();
  });

  // 編集は行の enabled を初期値にする（正常系）
  test("enabled_switch_when_edit", async ({ page }) => {
    await open(page, {
      settings: withSources(settingsSource("sample", { enabled: false, status: "disabled" })),
    });
    await openEdit(page, "sample");
    await expect(dialog(page).getByRole("switch", { name: "配信する" })).not.toBeChecked();
  });
});

test.describe("読み取りの範囲の入力欄", () => {
  // プレースホルダ・補助文を出し、追加は空にする（正常系）
  test("read_input_when_add", async ({ page }) => {
    await open(page);
    await openAdd(page);
    const input = page.getByLabel("読み取りの範囲");
    await expect(input).toHaveValue("");
    await expect(input).toHaveAttribute("placeholder", "~/repo/**");
    await expect(
      dialog(page).getByText("glob を 1 行に 1 つ。当たる作業場所から、この配信元の文書を読めます。"),
    ).toBeVisible();
  });

  // 編集は行の scope.read を 1 行に 1 つ入れる（正常系）
  test("read_input_when_edit", async ({ page }) => {
    await open(page, {
      settings: withSources(
        settingsSource("sample", { scope: { read: ["/a/**", "/b/**"], write: null } }),
      ),
    });
    await openEdit(page, "sample");
    await expect(page.getByLabel("読み取りの範囲")).toHaveValue("/a/**\n/b/**");
  });
});

test.describe("書き込みの範囲の入力欄", () => {
  // 任意の表示・補助文を出し、追加は空にする（正常系）
  test("write_input_when_add", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await expect(page.getByLabel("書き込みの範囲")).toHaveValue("");
    await expect(dialog(page).getByText("任意")).toBeVisible();
    await expect(
      dialog(page).getByText("glob を 1 行に 1 つ。当たる作業場所から、この配信元の文書へ書き込めます。"),
    ).toBeVisible();
  });

  // 編集は行の scope.write を 1 行に 1 つ入れ、空なら送信しない（正常系）
  test("write_input_when_edit", async ({ page }) => {
    // 準備
    const api = await open(page, {
      settings: withSources(
        settingsSource("sample", { scope: { read: ["/a/**"], write: ["/w/**", "/x/**"] } }),
      ),
    });
    await openEdit(page, "sample");
    await expect(page.getByLabel("書き込みの範囲")).toHaveValue("/w/**\n/x/**");
    // 実行
    await page.getByLabel("書き込みの範囲").fill("");
    await dialog(page).getByRole("button", { name: "保存" }).click();
    // 検証
    await expect(dialog(page)).toHaveCount(0);
    const body = api.callsOf("putSettings")[0]?.request.body as {
      sources: { scope: Record<string, unknown> }[];
    };
    expect(body.sources[0]?.scope).toEqual({ read: ["/a/**"] });
  });
});

test.describe("配信元のダイアログのキャンセル", () => {
  // クリックで入力を捨てて閉じ、開いたボタンへフォーカスを戻す（正常系）
  test("cancel_button", async ({ page }) => {
    // 準備
    await open(page);
    await openAdd(page);
    await page.getByLabel("配信元の ID").fill("abc");
    // 実行
    await dialog(page).getByRole("button", { name: "キャンセル" }).click();
    // 検証
    await expect(dialog(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "配信元を追加" })).toBeFocused();
    await openAdd(page);
    await expect(page.getByLabel("配信元の ID")).toHaveValue("");
  });

  // Esc で閉じ、開いたボタンへフォーカスを戻す（正常系）
  test("cancel_by_escape", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "配信元を追加" })).toBeFocused();
  });
});

test.describe("追加・保存ボタン", () => {
  // 追加は `追加`、編集は `保存` のラベルを出す（正常系）
  test("submit_label", async ({ page }) => {
    await open(page);
    await openAdd(page);
    await expect(dialog(page).getByRole("button", { name: "追加", exact: true })).toBeVisible();
    await dialog(page).getByRole("button", { name: "キャンセル" }).click();
    await openEdit(page, "sample");
    await expect(dialog(page).getByRole("button", { name: "保存", exact: true })).toBeVisible();
  });

  // 追加は今の一覧に入力を反映した sources[] を丸ごと送信し、200 でダイアログを閉じて一覧を取り直し通知を出す（正常系）
  test("submit_add_success", async ({ page }) => {
    // 準備
    let saved = false;
    const api = await open(page, {
      settings: () => ({
        body: settingsView(
          saved
            ? [settingsSource("sample"), settingsSource("knowledge"), settingsSource("extra")]
            : [settingsSource("sample"), settingsSource("knowledge")],
        ),
      }),
      putSettings: () => {
        saved = true;
        return { body: { sources: [] } };
      },
    });
    await openAdd(page);
    await fillValid(page);
    // 実行
    await dialog(page).getByRole("button", { name: "追加", exact: true }).click();
    // 検証
    await expect(dialog(page)).toHaveCount(0);
    await expect(page.getByText(TOAST)).toBeVisible();
    await expect(page.getByRole("link", { name: "extra" })).toBeVisible();
    const body = api.callsOf("putSettings")[0]?.request.body as {
      sources: { id: string }[];
    };
    expect(body.sources.map((row) => row.id)).toEqual(["sample", "knowledge", "extra"]);
  });

  // 保存の応答を待つ間はボタンを押せなくする（正常系）
  test("submit_disabled_while_saving", async ({ page }) => {
    // 準備
    await open(page, {
      putSettings: () => ({ body: { sources: [] }, delayMs: 1500 }),
    });
    await openAdd(page);
    await fillValid(page);
    const submit = dialog(page).getByRole("button", { name: "追加", exact: true });
    // 実行
    await submit.click();
    // 検証
    await expect(submit).toBeDisabled();
    await expect(dialog(page)).toHaveCount(0);
  });

  // 422 ならダイアログを開いたまま、保存の失敗のまとめと項目のエラーを出す（異常系）
  test("submit_failure_422", async ({ page }) => {
    // 準備
    await open(page, {
      putSettings: () =>
        problem(422, {
          errors: [{ path: "sources[2].config", reason: "設定ファイルが見つかりません" }],
        }),
    });
    await openAdd(page);
    await fillValid(page);
    // 実行
    await dialog(page).getByRole("button", { name: "追加", exact: true }).click();
    // 検証
    await expect(dialog(page)).toBeVisible();
    await expect(dialog(page).getByText("設定ファイルが見つかりません").first()).toBeVisible();
    await expect(page.getByText(TOAST)).toHaveCount(0);
  });
});

test.describe("保存の失敗のまとめ", () => {
  // 入力チェックに引っかかったとき、`保存できませんでした（{件数} 件）` を出す（異常系）
  test("failure_summary_when_invalid", async ({ page }) => {
    // 準備
    await open(page);
    await openAdd(page);
    // 実行
    await dialog(page).getByRole("button", { name: "追加", exact: true }).click();
    // 検証
    await expect(dialog(page).getByRole("alert")).toContainText("保存できませんでした（3 件）");
  });

  // 422 のとき、違反ごとに項目のエラーの文言と path を出す（異常系）
  test("failure_summary_when_422", async ({ page }) => {
    // 準備
    await open(page, {
      putSettings: () =>
        problem(422, {
          errors: [
            { path: "sources[2].config", reason: "設定ファイルが見つかりません。" },
            { path: "sources[2].scope.read", reason: "空の文字列があります。" },
          ],
        }),
    });
    await openAdd(page);
    await fillValid(page);
    // 実行
    await dialog(page).getByRole("button", { name: "追加", exact: true }).click();
    // 検証
    const alert = dialog(page).getByRole("alert");
    await expect(alert).toContainText("保存できませんでした（2 件）");
    await expect(alert).toContainText("設定ファイルが見つかりません");
    await expect(alert.locator("code", { hasText: "sources[2].config" })).toHaveClass(/font-mono/);
    await expect(alert).toBeFocused();
  });

  // 違反の行のクリックでその入力欄へフォーカスを移す（正常系）
  test("failure_summary_row_click", async ({ page }) => {
    // 準備
    await open(page, {
      putSettings: () =>
        problem(422, {
          errors: [{ path: "sources[2].scope.read", reason: "空の文字列があります。" }],
        }),
    });
    await openAdd(page);
    await fillValid(page);
    await dialog(page).getByRole("button", { name: "追加", exact: true }).click();
    // 実行
    await dialog(page).getByRole("alert").getByText("空の文字列があります").click();
    // 検証
    await expect(page.getByLabel("読み取りの範囲")).toBeFocused();
  });
});

test.describe("削除の確認", () => {
  // タイトルに `{id} を削除しますか?` を出す（正常系）
  test("delete_title", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "sample を削除" }).click();
    await expect(page.getByRole("alertdialog").getByRole("heading", { name: "sample を削除しますか?" })).toBeVisible();
  });

  // 説明に削除で起きることと起きないことを出す（正常系）
  test("delete_description", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "sample を削除" }).click();
    await expect(
      page.getByRole("alertdialog").getByText(
        "端末の設定から sample の行を削除し、配信から外します。フォルダ /home/me/sample と文書は削除しません。",
      ),
    ).toBeVisible();
  });

  // キャンセルに初期フォーカスがあり、クリックと Esc で閉じて削除ボタンへフォーカスを戻す（正常系）
  test("delete_cancel", async ({ page }) => {
    // 準備
    await open(page);
    const trigger = page.getByRole("button", { name: "sample を削除" });
    await trigger.click();
    const cancel = page.getByRole("alertdialog").getByRole("button", { name: "キャンセル" });
    await expect(cancel).toBeFocused();
    // 実行
    await page.keyboard.press("Escape");
    // 検証
    await expect(page.getByRole("alertdialog")).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  // 確定でその行を除いた sources[] を丸ごと送信し、200 で閉じて一覧を取り直し通知を出す（正常系）
  test("delete_confirm_success", async ({ page }) => {
    // 準備
    let removed = false;
    const api = await open(page, {
      settings: () => ({
        body: settingsView(
          removed ? [settingsSource("knowledge")] : [settingsSource("sample"), settingsSource("knowledge")],
        ),
      }),
      putSettings: () => {
        removed = true;
        return { body: { sources: [] } };
      },
    });
    await page.getByRole("button", { name: "sample を削除" }).click();
    // 実行
    await page.getByRole("alertdialog").getByRole("button", { name: "削除" }).click();
    // 検証
    await expect(page.getByRole("alertdialog")).toHaveCount(0);
    await expect(page.getByText(TOAST)).toBeVisible();
    await expect(page.getByRole("button", { name: "sample を削除" })).toHaveCount(0);
    const body = api.callsOf("putSettings")[0]?.request.body as {
      sources: { id: string }[];
    };
    expect(body.sources.map((row) => row.id)).toEqual(["knowledge"]);
  });

  // 失敗したらダイアログに Problem Details の detail を出す（異常系）
  test("delete_confirm_failure", async ({ page }) => {
    // 準備
    await open(page, {
      putSettings: () => problem(500, { detail: "端末の設定を書き込めませんでした" }),
    });
    await page.getByRole("button", { name: "sample を削除" }).click();
    // 実行
    await page.getByRole("alertdialog").getByRole("button", { name: "削除" }).click();
    // 検証
    await expect(page.getByRole("alertdialog")).toContainText("端末の設定を書き込めませんでした");
  });

  // 保存の応答を待つ間は削除ボタンを押せなくする（正常系）
  test("delete_confirm_disabled_while_saving", async ({ page }) => {
    await open(page, {
      putSettings: () => ({ body: { sources: [] }, delayMs: 1500 }),
    });
    await page.getByRole("button", { name: "sample を削除" }).click();
    const confirm = page.getByRole("alertdialog").getByRole("button", { name: "削除" });
    await confirm.click();
    await expect(confirm).toBeDisabled();
  });
});

test.describe("入力チェック", () => {
  const submitEmpty = async (page: Page) => {
    await open(page);
    await openAdd(page);
  };
  const submit = (page: Page) =>
    dialog(page).getByRole("button", { name: "追加", exact: true }).click();

  // 配信元の ID が空のとき、入力欄の下にエラーを出す（異常系）
  test("id_input_check_when_empty", async ({ page }) => {
    await submitEmpty(page);
    await submit(page);
    await expect(dialog(page).getByText("配信元の ID を入力してください。")).toBeVisible();
  });

  // 英小文字・数字・ハイフン以外の文字があるとき、エラーを出す（異常系）
  test("id_input_check_when_invalid_char", async ({ page }) => {
    await submitEmpty(page);
    await page.getByLabel("配信元の ID").fill("Sample_1");
    await submit(page);
    await expect(
      dialog(page).getByText("配信元の ID に使えない文字があります。英小文字・数字・ハイフンで入力してください。"),
    ).toBeVisible();
  });

  // 他の行の ID と重なるとき、エラーを出す（異常系）
  test("id_input_check_when_duplicated", async ({ page }) => {
    await submitEmpty(page);
    await page.getByLabel("配信元の ID").fill("sample");
    await submit(page);
    await expect(
      dialog(page).getByText("配信元の ID sample は既に使われています。別の ID を入力してください。"),
    ).toBeVisible();
  });

  // 一度出た後は入力のたびに検証する（異常系）
  test("id_input_check_revalidates_on_input", async ({ page }) => {
    await submitEmpty(page);
    await submit(page);
    const message = dialog(page).getByText("配信元の ID を入力してください。");
    await expect(message).toBeVisible();
    await page.getByLabel("配信元の ID").fill("ok");
    await expect(message).toHaveCount(0);
  });

  // 設定ファイルが空の行しか無いとき、エラーを出す（異常系）
  test("config_input_check_when_blank", async ({ page }) => {
    await submitEmpty(page);
    await page.getByLabel("設定ファイル").fill("\n  \n");
    await submit(page);
    await expect(dialog(page).getByText("設定ファイルを 1 つ以上入力してください。")).toBeVisible();
  });

  // 読み取りの範囲が空の行しか無いとき、エラーを出す（異常系）
  test("read_input_check_when_blank", async ({ page }) => {
    await submitEmpty(page);
    await submit(page);
    await expect(dialog(page).getByText("読み取りの範囲を 1 つ以上入力してください。")).toBeVisible();
  });

  // 読み取りの範囲に空の行を含むとき、エラーを出す（異常系）
  test("read_input_check_when_contains_blank", async ({ page }) => {
    await submitEmpty(page);
    await page.getByLabel("読み取りの範囲").fill("/a/**\n\n/b/**");
    await submit(page);
    await expect(
      dialog(page).getByText("読み取りの範囲に空の行があります。空の行を削除してください。"),
    ).toBeVisible();
  });

  // 書き込みの範囲に空の行を含むとき、エラーを出す（異常系）
  test("write_input_check_when_contains_blank", async ({ page }) => {
    await submitEmpty(page);
    await page.getByLabel("書き込みの範囲").fill("/a/**\n\n/b/**");
    await submit(page);
    await expect(
      dialog(page).getByText("書き込みの範囲に空の行があります。空の行を削除してください。"),
    ).toBeVisible();
  });
});
