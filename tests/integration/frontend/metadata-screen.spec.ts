import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route, expect, test } from "@playwright/test";

import { mockApi, problem } from "./support/api-mock";

const SOURCE = "sample";
const METADATA_PATH = `/_api/sources/${SOURCE}/metadata`;
const COMMITS_PATH = `/_api/sources/${SOURCE}/commits`;
const SHA = "0a1b2c3d4e5f";

type Row = {
  id: string;
  docKind: string | null;
  docPath: string | null;
  version: string | null;
  editable: boolean;
  values: Record<string, string | string[]>;
};

type CommitReply = { status: number; body: unknown };

const column = (key: string, label: string, overrides: Record<string, unknown> = {}) => ({
  key,
  label,
  type: "text",
  editable: true,
  ...overrides,
});

const kind = (id: string, title: string, overrides: Record<string, unknown> = {}) => ({
  id,
  title,
  served: true,
  hint: null,
  columns: [],
  canAdd: false,
  canDelete: false,
  createKind: null,
  rows: [] as Row[],
  ...overrides,
});

const row = (id: string, values: Row["values"], overrides: Partial<Row> = {}): Row => ({
  id,
  docKind: "note",
  docPath: `docs/note/${id}.yaml`,
  version: `v-${id}`,
  editable: true,
  values,
  ...overrides,
});

const metadataResponse = (overrides: { rulesServed?: boolean } = {}) => ({
  source: SOURCE,
  branch: "develop",
  kinds: [
    kind("terms", "用語集", {
      columns: [column("name", "用語"), column("aliases", "別名", { type: "list" }), column("description", "説明")],
      canAdd: true,
      canDelete: true,
      createKind: "terms",
      rows: [
        row("source", { name: "配信元", aliases: ["source"], description: "フォルダ" }, { docKind: "terms", docPath: "glossary.yaml" }),
        row("old-name", { name: "旧称", aliases: [], description: "使用しない呼び名" }, { docKind: "terms", docPath: "glossary.yaml" }),
      ],
    }),
    kind("aliases", "エイリアス", {
      columns: [column("name", "名前"), column("aliases", "別名", { type: "list" }), column("path", "文書", { editable: false })],
      rows: [row("n1", { name: "直コミット", aliases: [], path: "docs/note/n1.yaml" })],
    }),
    kind("tags", "タグ", {
      columns: [column("path", "文書", { editable: false }), column("tags", "タグ", { type: "list" })],
      rows: [row("n1", { path: "docs/note/n1.yaml", tags: ["topic:a"] })],
    }),
    overrides.rulesServed === false
      ? kind("rules", "rule-inject の索引", { served: false, hint: "documents:\n  - id: rule_index\n    paths: [rules.yaml]\n    records: rules" })
      : kind("rules", "rule-inject の索引", {
          columns: [column("rule", "規約"), column("paths", "適用するパス", { type: "list" })],
          rows: [row("r1", { rule: "docs/rule/a.yaml", paths: ["**/*.py"] }, { docKind: "rule_index", docPath: "rules.yaml", editable: false })],
        }),
    kind("config", "配信元の設定", {
      columns: [column("id", "種類", { editable: false })],
      rows: [row("note", { id: "note" }, { docKind: null, docPath: null, version: null, editable: false })],
    }),
    kind("files", "管理用の YAML", {
      columns: [column("path", "ファイル", { editable: false }), column("description", "概要")],
      rows: [row("f1", { path: "src/app.py", description: "アプリの組み立て" }, { docKind: "files", docPath: "src/app.py" })],
    }),
  ],
});

/** メタデータの取得と直コミットを差し替えて画面を開く。直コミットの要求の本文を返却する */
const open = async (
  page: Page,
  options: { metadata?: ReturnType<typeof metadataResponse>; commit?: (dryRun: boolean) => CommitReply; url?: string } = {},
) => {
  await mockApi(page);
  const commits: Record<string, unknown>[] = [];
  let metadataCalls = 0;
  await page.route(`**${METADATA_PATH}`, async (route: Route) => {
    metadataCalls += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(options.metadata ?? metadataResponse()) });
  });
  await page.route(`**${COMMITS_PATH}`, async (route: Route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    commits.push(body);
    const reply = (options.commit ?? committed)(body.dryRun === true);
    await route.fulfill({
      status: reply.status,
      contentType: reply.status >= 400 ? "application/problem+json" : "application/json",
      body: JSON.stringify(reply.body),
    });
  });
  await page.goto(options.url ?? `/${SOURCE}/_metadata`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`${SOURCE} のメタデータ`);
  return { commits, metadataCalls: () => metadataCalls };
};

const committed = (dryRun: boolean): CommitReply => ({
  status: 200,
  body: {
    applied: !dryRun,
    results: [{ key: "tags:n1:update", status: "updated", version: "v2", diff: "-   - topic:a\n+   - topic:a\n+   - topic:b" }],
    commit: dryRun ? null : { sha: SHA, branch: "develop", retried: false },
  },
});

const panel = (page: Page) => page.getByRole("complementary", { name: "編集中" }).or(page.getByRole("dialog", { name: "編集中" }));

/** タグのタブで n1 のタグを修正する */
const editTag = async (page: Page, tags: string) => {
  await page.getByRole("tab", { name: /タグ/ }).click();
  await page.getByRole("button", { name: "タグ topic:a を編集" }).click();
  const input = page.getByRole("textbox", { name: "タグ" });
  await input.fill(tags);
  await input.press("Enter");
};

/** 編集中のパネルからコミットの確認を経てコミットする */
const commitFromPanel = async (page: Page, message: string) => {
  await panel(page).getByRole("button", { name: /^(コミット|再試行)$/ }).click();
  const dialog = page.getByRole("dialog", { name: "コミットしますか？" });
  await dialog.getByRole("textbox", { name: "コミットの説明" }).fill(message);
  await dialog.getByRole("button", { name: "コミット" }).click();
};

test.describe("ページのタイトルと種類のタブ", () => {
  // タイトルを `メタデータ | {配信元} | dev-docs` にし、6 つの種類のタブと用語集の表を出す（正常系）
  test("page_title", async ({ page }) => {
    await open(page);
    await expect(page).toHaveTitle(`メタデータ | ${SOURCE} | dev-docs`);
    await expect(page.getByRole("tab")).toHaveCount(6);
    await expect(page.getByRole("tab", { name: /用語集/, selected: true })).toBeVisible();
    await expect(page.getByRole("table", { name: "用語集の表" })).toContainText("配信元");
  });

  // タブの切り替えを URL の `tab` に保ち、開き直すとそのタブを選ぶ（正常系）
  test("tab_in_url", async ({ page }) => {
    await open(page);
    await page.getByRole("tab", { name: /管理用の YAML/ }).click();
    await expect(page).toHaveURL(/tab=files/);
    await page.reload();
    await expect(page.getByRole("tab", { name: /管理用の YAML/, selected: true })).toBeVisible();
  });
});

test.describe("絞り込み", () => {
  // 値に入力を含む行だけにし、該当する行が無ければその旨を出す（正常系）
  test("filter_rows", async ({ page }) => {
    await open(page);
    const filter = page.getByRole("searchbox", { name: "絞り込み" });
    await filter.fill("旧称");
    const table = page.getByRole("table", { name: "用語集の表" });
    await expect(table).toContainText("旧称");
    await expect(table).not.toContainText("配信元");
    await filter.fill("存在しない");
    await expect(page.getByText("「存在しない」に一致する行はありません。")).toBeVisible();
  });
});

test.describe("種類を配信していない・参照のみ", () => {
  // 配信していない種類は配信元の設定に追加する行を出す（正常系）
  test("kind_not_served", async ({ page }) => {
    await open(page, { metadata: metadataResponse({ rulesServed: false }) });
    await page.getByRole("tab", { name: /rule-inject の索引/ }).click();
    await expect(page.getByText("rule-inject の索引を配信していません")).toBeVisible();
    await expect(page.getByText("records: rules")).toBeVisible();
  });

  // 全ての行が修正できない種類は参照のみの表示を出し、値をボタンにしない（正常系）
  test("read_only_kind", async ({ page }) => {
    await open(page);
    await page.getByRole("tab", { name: /rule-inject の索引/ }).click();
    await expect(page.getByText("この種類は直コミットを許可していないため、参照のみです。")).toBeVisible();
    await expect(page.getByRole("button", { name: /を編集$/ })).toHaveCount(0);
  });
});

test.describe("編集・差分確認・コミット", () => {
  // 修正をトップバーの件数に出し、差分確認で差分を出してから、コミットで説明と変更を送信して編集中を空にする（正常系）
  test("commit_edits", async ({ page }) => {
    // 準備
    const api = await open(page);
    await editTag(page, "topic:a, topic:b");
    await expect(page.getByRole("button", { name: "編集中 1 件" })).toBeVisible();
    await page.getByRole("button", { name: "編集中 1 件" }).click();
    // 実行（差分確認）
    await panel(page).getByRole("button", { name: "差分確認" }).click();
    // 検証（差分確認）
    await expect(panel(page)).toContainText("+   - topic:b");
    expect(api.commits[0]).toMatchObject({ dryRun: true });
    // 実行（コミット）
    const before = api.metadataCalls();
    await commitFromPanel(page, "タグを追加する");
    // 検証（コミット）
    await expect(panel(page).getByText(`develop にコミットしました（${SHA.slice(0, 7)}）`)).toBeVisible();
    expect(api.commits[1]).toMatchObject({
      dryRun: false,
      message: "タグを追加する",
      edits: [{ key: "tags:n1:update", kind: "tags", op: "update", docId: "n1", docKind: "note", expectedVersion: "v-n1", values: { tags: ["topic:a", "topic:b"] } }],
    });
    expect(api.commits[1]?.edits).toEqual([expect.not.objectContaining({ docPath: expect.anything() })]);
    await expect(page.getByRole("button", { name: "編集中 0 件" })).toBeVisible();
    await expect.poll(api.metadataCalls).toBeGreaterThan(before);
  });

  // 行の追加と削除を編集中の変更にし、元に戻すで変更から除く（正常系）
  test("add_and_delete_rows", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "行追加" }).click();
    await expect(page.getByRole("textbox", { name: "ID" })).toBeFocused();
    await page.getByRole("textbox", { name: "ID" }).fill("kind");
    await page.getByRole("textbox", { name: "用語" }).fill("種類");
    await page.getByRole("button", { name: "追加", exact: true }).click();
    await page.getByRole("button", { name: "旧称 を削除" }).click();
    await expect(page.getByRole("button", { name: "編集中 2 件" })).toBeVisible();
    await page.getByRole("button", { name: "旧称 を元に戻す" }).click();
    await expect(page.getByRole("button", { name: "編集中 1 件" })).toBeVisible();
  });

  // 追加の行の ID の入力チェックに当たると変更にしない（異常系）
  test("add_row_invalid_id", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "行追加" }).click();
    await page.getByRole("textbox", { name: "ID" }).fill("Bad ID");
    await page.getByRole("button", { name: "追加", exact: true }).click();
    await expect(page.getByRole("button", { name: "編集中 0 件" })).toBeVisible();
  });

  // 編集中の変更を再読み込みしても残す（正常系）
  test("keep_edits_on_reload", async ({ page }) => {
    await open(page);
    await editTag(page, "topic:b");
    await page.reload();
    await expect(page.getByRole("button", { name: "編集中 1 件" })).toBeVisible();
  });

  // パネルの変更の行から、その種類のタブの行へ移動する（正常系）
  test("locate_edit", async ({ page }) => {
    await open(page);
    await editTag(page, "topic:b");
    await page.getByRole("tab", { name: /用語集/ }).click();
    await page.getByRole("button", { name: "編集中 1 件" }).click();
    await panel(page).getByRole("button", { name: "タグ: docs/note/n1.yaml の行へ移動" }).click();
    await expect(page.getByRole("tab", { name: /タグ/, selected: true })).toBeVisible();
    await expect(page.locator("#metadata-row-tags-n1")).toBeFocused();
  });
});

test.describe("送信の失敗", () => {
  // 422 の理由を変更の行の下に出し、編集中の変更を残して再試行にする（異常系）
  test("validation_failed", async ({ page }) => {
    // 準備
    await open(page, {
      commit: () =>
        problem(422, {
          title: "EditsRejectedError",
          detail: "検査に合格しませんでした",
          errors: [{ key: "tags:n1:update", path: "tags[1]", reason: "topic: で始まりません" }],
        }) as CommitReply,
    });
    await editTag(page, "topic:a, 使用できないタグ");
    await page.getByRole("button", { name: "編集中 1 件" }).click();
    // 実行
    await commitFromPanel(page, "タグを追加する");
    // 検証
    const alert = panel(page).getByRole("alert");
    await expect(alert).toContainText("コミットできませんでした。変更ごとの理由を確認してください。");
    await expect(alert).toContainText("編集中の変更はそのままです。");
    await expect(panel(page)).toContainText("tags[1]: topic: で始まりません");
    await expect(panel(page).getByRole("button", { name: "再試行" })).toBeVisible();
    await expect(page.getByRole("button", { name: "編集中 1 件" })).toBeVisible();
  });

  // 409 の今のバージョンを変更の行に出す（異常系）
  test("version_mismatch", async ({ page }) => {
    await open(page, {
      commit: () =>
        problem(409, {
          title: "EditsRejectedError",
          detail: "参照した後に変わった文書があります",
          nextSteps: ["メタデータを再読み込みし、変更が反映されたかを確認してください。"],
          errors: [{ key: "tags:n1:update", path: "", reason: "参照した後に文書が変わっています", current: "9f8e7d" }],
        }) as CommitReply,
    });
    await editTag(page, "topic:b");
    await page.getByRole("button", { name: "編集中 1 件" }).click();
    await commitFromPanel(page, "タグを修正する");
    await expect(panel(page)).toContainText("今のバージョン 9f8e7d");
    await expect(panel(page).getByRole("alert")).toContainText("メタデータを再読み込みし");
  });
});

test.describe("project-index から受け取れない", () => {
  // メタデータの取得の 503 で接続先と理由と再読み込みを出す（異常系）
  test("project_index_unreachable", async ({ page }) => {
    await mockApi(page);
    await page.route(`**${METADATA_PATH}`, (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/problem+json",
        body: JSON.stringify(
          problem(503, {
            title: "ProjectIndexUnreachableError",
            projectIndex: { address: "http://127.0.0.1:8786", reason: "接続を拒否されました", kind: "unreachable" },
          }).body,
        ),
      }),
    );
    await page.goto(`/${SOURCE}/_metadata`);
    await expect(page.getByText("http://127.0.0.1:8786")).toBeVisible();
    await expect(page.getByText("接続を拒否されました")).toBeVisible();
    await expect(page.getByRole("button", { name: "再読み込み" })).toBeVisible();
  });
});

test.describe("狭い幅とアクセシビリティ", () => {
  // 狭い幅で画面を横にスクロールさせず、表の領域だけを横にスクロールする（正常系）
  test("narrow_viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  // 表と編集中のパネルを開いた画面に axe の違反が無い（正常系）
  test("axe", async ({ page }) => {
    await open(page);
    await editTag(page, "topic:b");
    await page.getByRole("button", { name: "編集中 1 件" }).click();
    await expect(panel(page)).toBeVisible();
    // パネルの開くアニメーションの途中の色で判定しない
    await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState !== "running"));
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(result.violations.map((violation) => violation.id)).toEqual([]);
  });
});
