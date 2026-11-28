import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route, expect, test } from "@playwright/test";

import { mockApi, problem } from "./support/api-mock";

const SOURCE = "sample";
const METADATA_PATH = `/_api/sources/${SOURCE}/metadata`;
const COMMITS_PATH = `/_api/sources/${SOURCE}/commits`;
const SHA = "0a1b2c3d4e5f";
const BASE_COMMIT = "5765b2e1f0a9";
const LATEST_COMMIT = "7f9a8781b2c3";

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

const metadataResponse = (overrides: { rulesServed?: boolean; baseCommit?: string; tags?: string[] } = {}) => ({
  source: SOURCE,
  branch: "develop",
  baseCommit: overrides.baseCommit ?? BASE_COMMIT,
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
      rows: [row("n1", { path: "docs/note/n1.yaml", tags: overrides.tags ?? ["topic:a"] })],
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
  options: {
    metadata?: ReturnType<typeof metadataResponse>;
    // 直コミットを送信した後の、`ref` を省いた（既定のブランチの先頭の）取得への応答
    latest?: ReturnType<typeof metadataResponse>;
    commit?: (dryRun: boolean) => CommitReply;
    url?: string;
  } = {},
) => {
  await mockApi(page);
  const commits: Record<string, unknown>[] = [];
  const metadataRefs: (string | null)[] = [];
  let metadataCalls = 0;
  await page.route(
    (url) => url.pathname === METADATA_PATH,
    async (route: Route) => {
      metadataCalls += 1;
      const ref = new URL(route.request().url()).searchParams.get("ref");
      metadataRefs.push(ref);
      const body = ref === null && commits.length > 0 && options.latest ? options.latest : (options.metadata ?? metadataResponse());
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    },
  );
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
  return { commits, metadataRefs, metadataCalls: () => metadataCalls };
};

const committed = (dryRun: boolean): CommitReply => ({
  status: 200,
  body: {
    applied: !dryRun,
    results: [{ key: "tags:n1:update", status: "updated", version: "v2", diff: "-   - topic:a\n+   - topic:a\n+   - topic:b" }],
    commit: dryRun ? null : { sha: SHA, branch: "develop", retried: false },
  },
});

const panel = (page: Page) => page.getByRole("complementary", { name: "レビュー中" }).or(page.getByRole("dialog", { name: "レビュー中" }));

/** タグのタブで n1 のタグを修正する */
const editTag = async (page: Page, tags: string) => {
  await page.getByRole("tab", { name: /タグ/ }).click();
  await page.getByRole("button", { name: "タグ topic:a を編集" }).click();
  const input = page.getByRole("textbox", { name: "タグ" });
  await input.fill(tags);
  await input.press("Enter");
};

/** レビュー中のパネルからコミットの確認を経てコミットする */
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
  // 修正をトップバーの件数に出し、差分確認で差分を出してから、コミットで説明と変更を送信してレビュー中のパネルを空にする（正常系）
  test("commit_edits", async ({ page }) => {
    // 準備
    const api = await open(page);
    await editTag(page, "topic:a, topic:b");
    await expect(page.getByRole("button", { name: "レビュー中 1 件" })).toBeVisible();
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
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
      baseCommit: BASE_COMMIT,
      edits: [
        {
          key: "tags:n1:update",
          kind: "tags",
          op: "update",
          docId: "n1",
          docKind: "note",
          expectedVersion: "v-n1",
          docPath: "docs/note/n1.yaml",
          values: { tags: ["topic:a", "topic:b"] },
        },
      ],
    });
    await expect(page.getByRole("button", { name: "レビュー中", exact: true })).toBeVisible();
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
    await expect(page.getByRole("button", { name: "レビュー中 2 件" })).toBeVisible();
    await page.getByRole("button", { name: "旧称 を元に戻す" }).click();
    await expect(page.getByRole("button", { name: "レビュー中 1 件" })).toBeVisible();
  });

  // 追加の行の ID の入力チェックに当たると変更にしない（異常系）
  test("add_row_invalid_id", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "行追加" }).click();
    await page.getByRole("textbox", { name: "ID" }).fill("Bad ID");
    await page.getByRole("button", { name: "追加", exact: true }).click();
    await expect(page.getByRole("button", { name: "レビュー中", exact: true })).toBeVisible();
  });

  // 編集中の変更を再読み込みしても残す（正常系）
  test("keep_edits_on_reload", async ({ page }) => {
    await open(page);
    await editTag(page, "topic:b");
    await page.reload();
    await expect(page.getByRole("button", { name: "レビュー中 1 件" })).toBeVisible();
  });

  // パネルの変更の行から、その種類のタブの行へ移動する（正常系）
  test("locate_edit", async ({ page }) => {
    await open(page);
    await editTag(page, "topic:b");
    await page.getByRole("tab", { name: /用語集/ }).click();
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
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
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    // 実行
    await commitFromPanel(page, "タグを追加する");
    // 検証
    const alert = panel(page).getByRole("alert");
    await expect(alert).toContainText("コミットできませんでした。変更ごとの理由を確認してください。");
    await expect(alert).toContainText("編集中の変更はそのままです。");
    await expect(panel(page)).toContainText("tags[1]: topic: で始まりません");
    await expect(panel(page).getByRole("button", { name: "再試行" })).toBeVisible();
    await expect(page.getByRole("button", { name: "レビュー中 1 件" })).toBeVisible();
  });

  // 編集を始めたときのコミットを使えない 409 で「最新の内容で続ける」を出し、押すと最新の内容で再取得して食い違う変更を取り消す（異常系）
  test("base_commit_unusable", async ({ page }) => {
    // 準備
    const api = await open(page, {
      latest: metadataResponse({ baseCommit: LATEST_COMMIT, tags: ["topic:x"] }),
      commit: () =>
        problem(409, {
          title: "BaseCommitUnusableError",
          detail: "編集を始めたときのコミットがありません",
          errors: [],
        }) as CommitReply,
    });
    await editTag(page, "topic:b");
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    await commitFromPanel(page, "タグを修正する");
    await expect(panel(page).getByRole("alert")).toContainText("「最新の内容で続ける」を押すと");
    // 実行
    await panel(page).getByRole("button", { name: "最新の内容で続ける" }).click();
    // 検証
    const dropped = panel(page).getByRole("status");
    await expect(dropped).toContainText("最新の内容と食い違うため、次の変更を取り消しました");
    await expect(dropped).toContainText("タグ: docs/note/n1.yaml");
    await expect(dropped).toContainText("最新の値を確認して、もう一度編集してください。");
    expect(api.metadataRefs).toContain(null);
    expect(api.commits[0]?.baseCommit).toBe(BASE_COMMIT);
  });

  // 衝突してブランチに残した結果を出し、編集中の変更を空にしてメタデータを再取得する（正常系）
  test("conflict_kept_on_branch", async ({ page }) => {
    // 準備
    const api = await open(page, {
      commit: (dryRun) =>
        dryRun
          ? committed(true)
          : {
              status: 200,
              body: {
                applied: false,
                results: [],
                commit: null,
                conflict: {
                  branch: "project-index/conflict/20261123-142916-5765b2e",
                  baseCommit: BASE_COMMIT,
                  reasons: [{ key: "tags:n1:update", reason: "n1 は参照した後に変わっています" }],
                  script: { exitCode: 0, timedOut: false, prUrl: "https://github.com/o/r/pull/9", stderr: "" },
                },
              },
            },
    });
    await editTag(page, "topic:b");
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    const before = api.metadataCalls();
    // 実行
    await commitFromPanel(page, "タグを修正する");
    // 検証
    const result = panel(page).getByRole("status");
    await expect(result).toContainText("ほかの変更と衝突したため、修正をブランチに残しました");
    await expect(result).toContainText("project-index/conflict/20261123-142916-5765b2e");
    await expect(result).toContainText("5765b2e");
    await expect(result.getByRole("link", { name: "PR を開く" })).toHaveAttribute("href", "https://github.com/o/r/pull/9");
    await expect(result).toContainText("タグ: docs/note/n1.yaml");
    await expect(result).toContainText("n1 は参照した後に変わっています");
    await expect(result).toContainText("ブランチに残した変更は、編集中の変更から除きました。");
    await expect(page.getByRole("button", { name: "レビュー中", exact: true })).toBeVisible();
    await expect.poll(() => api.metadataCalls()).toBeGreaterThan(before);
    expect(api.commits[0]).toMatchObject({ baseCommit: BASE_COMMIT });
    expect(api.commits[0]?.edits).toEqual([expect.objectContaining({ docPath: "docs/note/n1.yaml" })]);
  });

  // 差分確認が衝突を返却したら、コミットすると衝突することと変更ごとの理由を出す（正常系）
  test("dry_run_conflicted", async ({ page }) => {
    // 準備
    await open(page, {
      commit: () => ({
        status: 200,
        body: {
          applied: false,
          results: [],
          commit: null,
          conflict: {
            branch: null,
            baseCommit: BASE_COMMIT,
            reasons: [{ key: "tags:n1:update", reason: "n1 は参照した後に変わっています" }],
            script: null,
          },
        },
      }),
    });
    await editTag(page, "topic:b");
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    // 実行
    await panel(page).getByRole("button", { name: "差分確認" }).click();
    // 検証
    await expect(panel(page).getByRole("alert")).toContainText("コミットすると、ほかの変更と衝突して修正がブランチに残ります");
    await expect(panel(page)).toContainText("n1 は参照した後に変わっています");
    await expect(page.getByRole("button", { name: "レビュー中 1 件" })).toBeVisible();
  });
});

/** メタデータの取得を失敗の応答に差し替えて画面を開く */
const openFailed = async (page: Page, status: number, extra: Record<string, unknown>) => {
  await mockApi(page);
  await page.route(`**${METADATA_PATH}`, (route) =>
    route.fulfill({ status, contentType: "application/problem+json", body: JSON.stringify(problem(status, extra).body) }),
  );
  await page.goto(`/${SOURCE}/_metadata`);
};

test.describe("行が指す文書のリンク", () => {
  // 押すとその文書の文書の画面を開き、戻ると直前の種類のタブを選ぶ（正常系）
  test("open_row_document", async ({ page }) => {
    await open(page, { url: `/${SOURCE}/_metadata?tab=tags` });
    await page.getByRole("link", { name: "docs/note/n1.yaml" }).click();
    await expect(page).toHaveURL(new RegExp(`/${SOURCE}/docs/note/n1\\.yaml`));
    await page.goBack();
    await expect(page.getByRole("tab", { name: /タグ/, selected: true })).toBeVisible();
  });
});

test.describe("取得の失敗", () => {
  // メタデータの取得が 404 のとき、URL を変えずに見つからない画面を出す（異常系）
  test("source_not_found", async ({ page }) => {
    await openFailed(page, 404, { title: "UnknownSourceError", missing: "source", value: SOURCE });
    await expect(page.getByRole("heading", { name: `配信元 ${SOURCE} はありません` })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/${SOURCE}/_metadata$`));
  });

  // 404・503 以外の失敗で、取得できなかったことと再読み込みを出す（異常系）
  test("fetch_failed", async ({ page }) => {
    await openFailed(page, 500, { title: "InternalError" });
    await expect(page.getByText("メタデータを取得できませんでした")).toBeVisible();
    await expect(page.getByRole("button", { name: "再読み込み" })).toBeVisible();
  });
});

test.describe("キャンセル", () => {
  // 追加の行はキャンセルか Esc で閉じ、変更を作らずに行追加ボタンへフォーカスを戻す（正常系）
  for (const how of ["button", "escape"] as const) {
    test(`cancel_new_row_${how}`, async ({ page }) => {
      await open(page);
      await page.getByRole("button", { name: "行追加" }).click();
      await page.getByRole("textbox", { name: "ID" }).fill("kind");
      if (how === "button") await page.getByRole("button", { name: "キャンセル" }).click();
      else await page.keyboard.press("Escape");
      await expect(page.getByRole("textbox", { name: "ID" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "行追加" })).toBeFocused();
      await expect(page.getByRole("button", { name: "レビュー中", exact: true })).toBeVisible();
    });
  }

  // コミットの確認はキャンセルか Esc で閉じ、送信せずにコミットボタンへフォーカスを戻す（正常系）
  for (const how of ["button", "escape"] as const) {
    test(`cancel_commit_${how}`, async ({ page }) => {
      const api = await open(page);
      await editTag(page, "topic:b");
      await page.getByRole("button", { name: "レビュー中 1 件" }).click();
      await panel(page).getByRole("button", { name: "コミット" }).click();
      const dialog = page.getByRole("dialog", { name: "コミットしますか？" });
      await expect(dialog).toBeVisible();
      if (how === "button") await dialog.getByRole("button", { name: "キャンセル" }).click();
      else await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(panel(page).getByRole("button", { name: "コミット" })).toBeFocused();
      await expect(page.getByRole("button", { name: "レビュー中 1 件" })).toBeVisible();
      expect(api.commits).toHaveLength(0);
    });
  }
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

/** タグの n1 の値のボタンで、`index` 文字目の直前の点（文字の間）の座標 */
const pointBefore = async (page: Page, index: number) =>
  page.getByRole("button", { name: "タグ topic:a を編集" }).evaluate((button, at) => {
    const walker = document.createTreeWalker(button, NodeFilter.SHOW_TEXT);
    const node = walker.nextNode();
    if (node === null) throw new Error("値の文字がありません");
    const range = document.createRange();
    range.setStart(node, at);
    range.setEnd(node, at + 1);
    const rect = range.getBoundingClientRect();
    return { x: rect.left + 1, y: rect.top + rect.height / 2 };
  }, index);

test.describe("行の値の入力位置", () => {
  // 値の文字の間を押すと、その間に入力位置を配置する（正常系）
  test("row_value_caret_at_click", async ({ page }) => {
    await open(page, { url: `/${SOURCE}/_metadata?tab=tags` });
    const { x, y } = await pointBefore(page, 5);

    await page.mouse.click(x, y);

    const input = page.getByRole("textbox", { name: "タグ" });
    await expect(input).toBeFocused();
    expect(await input.evaluate((element: HTMLInputElement) => [element.selectionStart, element.selectionEnd])).toEqual([5, 5]);
  });

  // 値の右の余白を押すと末尾に入力位置を配置する（正常系）
  test("row_value_caret_at_right_space", async ({ page }) => {
    await open(page, { url: `/${SOURCE}/_metadata?tab=tags` });
    const button = page.getByRole("button", { name: "タグ topic:a を編集" });
    const box = await button.boundingBox();
    if (box === null) throw new Error("値のボタンが画面に出ていません");

    await page.mouse.click(box.x + box.width - 2, box.y + box.height / 2);

    const input = page.getByRole("textbox", { name: "タグ" });
    await expect(input).toBeFocused();
    expect(await input.evaluate((element: HTMLInputElement) => element.selectionStart)).toBe("topic:a".length);
  });

  // Enter・Space で始めると末尾に入力位置を配置する（正常系）
  for (const key of ["Enter", "Space"]) {
    test(`row_value_caret_on_${key.toLowerCase()}`, async ({ page }) => {
      await open(page, { url: `/${SOURCE}/_metadata?tab=tags` });
      await page.getByRole("button", { name: "タグ topic:a を編集" }).focus();

      await page.keyboard.press(key);

      const input = page.getByRole("textbox", { name: "タグ" });
      await expect(input).toBeFocused();
      expect(await input.evaluate((element: HTMLInputElement) => element.selectionStart)).toBe("topic:a".length);
    });
  }
});

test.describe("本文の幅", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  // 種類の表を、画面の横幅から左右の余白を除いた幅（上限なし）で出す（正常系）
  test("table_width_without_cap", async ({ page }) => {
    await open(page);
    const main = await page.getByRole("main").boundingBox();
    const table = await page.getByRole("table", { name: "用語集の表" }).boundingBox();
    if (main === null || table === null) throw new Error("本文か表が画面に出ていません");

    // 本文は画面の横幅いっぱいで、表は左右 1rem ずつの余白と表の枠線を除いた幅。72rem（1152px）の上限を超えて広がる
    expect(main.width).toBe(1920);
    expect(table.width).toBeGreaterThan(1152);
    expect(table.width).toBeGreaterThanOrEqual(1920 - 32 - 4);
    expect(table.width).toBeLessThanOrEqual(1920 - 32);
  });

  // 絞り込みの入力欄は 24rem までの幅にする（正常系）
  test("filter_width", async ({ page }) => {
    await open(page);
    const filter = await page.getByRole("searchbox", { name: "絞り込み" }).or(page.getByRole("textbox", { name: "絞り込み" })).boundingBox();
    if (filter === null) throw new Error("絞り込みの入力欄が画面に出ていません");

    expect(filter.width).toBeLessThanOrEqual(384);
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

  // 表とレビュー中のパネルを開いた画面に axe の違反が無い（正常系）
  test("axe", async ({ page }) => {
    await open(page);
    await editTag(page, "topic:b");
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    await expect(panel(page)).toBeVisible();
    // パネルの開くアニメーションの途中の色で判定しない
    await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState !== "running"));
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(result.violations.map((violation) => violation.id)).toEqual([]);
  });
});

/** 文書の本文の変更 1 件をブラウザのタブの編集中の変更に入れる */
const seedBodyEdit = async (page: Page, path: string, before: string, value: string) => {
  const edit = {
    key: `body:rule-sample:${path}`,
    kind: "body",
    op: "update",
    docId: "rule-sample",
    docKind: "rule",
    expectedVersion: "a1b2c3",
    docPath: "docs/rule/rule-sample.yaml",
    values: { [path]: value },
    before: { [path]: before },
    label: `${path === "@file" ? "ファイル全体" : "説明"}（docs/rule/rule-sample.yaml）`,
  };
  await page.addInitScript((stored) => {
    window.sessionStorage.setItem("dev-docs:pending-edits", stored);
  }, JSON.stringify({ state: { bySource: { [SOURCE]: [edit] }, baseCommitBySource: { [SOURCE]: BASE_COMMIT } }, version: 2 }));
};

test.describe("文書の本文の変更", () => {
  // 本文の変更の行は `{項目の名前}（{文書のパス}）` を出し、押すとその文書を編集の表示で開いてパネルを開いたままにする（正常系）
  test("locate_body_edit", async ({ page }) => {
    await seedBodyEdit(page, "description", "本文を編集する決まり", "修正後の説明");
    await open(page);
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    const row = panel(page).getByRole("button", { name: "説明（docs/rule/rule-sample.yaml） の行へ移動" });
    await expect(row).toContainText("本文を編集する決まり → 修正後の説明");
    await row.click();
    await expect(page).toHaveURL(/\/sample\/docs\/rule\/rule-sample\.yaml\?.*edit=fields/);
    await expect(panel(page)).toBeVisible();
  });

  // ファイル全体の変更の行は `edit=file` で開く（正常系）
  test("locate_whole_file_edit", async ({ page }) => {
    await seedBodyEdit(page, "@file", "id: rule-sample\n", "id: rule-sample\nname: 修正後\n");
    await open(page);
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    await panel(page).getByRole("button", { name: "ファイル全体（docs/rule/rule-sample.yaml） の行へ移動" }).click();
    await expect(page).toHaveURL(/\/sample\/docs\/rule\/rule-sample\.yaml\?.*edit=file/);
  });

  // 「最新の内容で続ける」で、本文の変更は文書を再取得し、変更前の値と食い違えば取り消す（異常系）
  test("restart_with_body_edit", async ({ page }) => {
    await seedBodyEdit(page, "description", "本文を編集する決まり", "修正後の説明");
    const api = await open(page, {
      commit: () =>
        problem(409, { title: "BaseCommitUnusableError", detail: "編集を始めたときのコミットがありません", errors: [] }) as CommitReply,
    });
    const documents: string[] = [];
    await page.route("**/_api/sources/sample/docs/**", async (route) => {
      documents.push(new URL(route.request().url()).pathname);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          source: SOURCE,
          ref: "develop",
          path: "docs/rule/rule-sample",
          markdown: "# 文書の編集",
          edit: {
            docId: "rule-sample",
            kind: "rule",
            filePath: "docs/rule/rule-sample.yaml",
            version: "b2c3d4",
            baseCommit: LATEST_COMMIT,
            language: "yaml",
            source: "id: rule-sample\n",
            blocks: [{ path: "description", label: "説明", type: "string", value: "ほかの変更の説明", markdown: "ほかの変更の説明", options: null, columns: null }],
            titleBlock: null,
          },
        }),
      });
    });
    await page.getByRole("button", { name: "レビュー中 1 件" }).click();
    await commitFromPanel(page, "説明を修正する");
    await panel(page).getByRole("button", { name: "最新の内容で続ける" }).click();
    const dropped = panel(page).getByRole("status");
    await expect(dropped).toContainText("最新の内容と食い違うため、次の変更を取り消しました");
    await expect(dropped).toContainText("説明（docs/rule/rule-sample.yaml）");
    expect(documents.some((path) => path.endsWith("/docs/docs/rule/rule-sample.yaml"))).toBe(true);
    expect(api.commits[0]?.edits).toMatchObject([{ kind: "body", values: { description: "修正後の説明" } }]);
  });
});
