import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";
import { expect, userEvent, within } from "storybook/test";

import { DocViewScreen } from "@/features/docs/doc-view/doc-view-screen";
import type { DocumentEdit as DocEdit } from "@/shared/api/generated/model";
import { type PendingEdit, usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { SIDEBAR_WIDTH, usePreferencesStore } from "@/shared/stores/preferences";

const DOCUMENT = "*/_api/sources/:source/docs/*";
const REFS = "*/_api/sources/:source/refs";
const SETTINGS = "*/_api/settings/sources";
const COMMITS = "*/_api/sources/:source/commits";

const page = (title: string, path: string) => ({
  kind: "page" as const,
  title,
  path,
  items: [],
  change: null,
});

const tabs = [
  {
    title: "設計書",
    active: true,
    items: [
      {
        kind: "group" as const,
        title: "画面",
        path: null,
        items: [
          page("文書の画面", "docs/a"),
          page("設定画面", "docs/b"),
          page("見つからない画面", "docs/c"),
        ],
        change: null,
      },
    ],
  },
  { title: "規約", active: false, items: [] },
];

const columns = Array.from({ length: 9 }, (_, i) => `列 ${i + 1}`);

const markdown = [
  "# 文書の画面",
  "",
  "## 概要",
  "",
  "1 文書の本文を、種類のタブ・サイドバー・パンくず・目次と一緒に参照する画面。画面が広いときは、本文と表がサイドバーを除いた画面の幅まで広がり、ブラウザの拡大率を下げるほど一度に表示できる量が増える。",
  "",
  "## 要素",
  "",
  `| 要素 | ${columns.join(" | ")} |`,
  `| --- | ${columns.map(() => "---").join(" | ")} |`,
  ...["トップバー", "種類のタブ", "文書の一覧", "パンくず", "本文"].map(
    (name) =>
      `| ${name} | ${columns.map((column) => `${name}の${column}の値`).join(" | ")} |`,
  ),
  "",
  "## 振る舞い",
  "",
  "- 画面幅 48rem 未満では、文書の一覧をドロワーにする",
  "- トップバー・種類のタブ・サイドバー・目次は、スクロールしても画面に残す",
  "",
].join("\n");

const documentResponse = (overrides: Record<string, unknown> = {}) => ({
  source: "sample",
  ref: "main",
  path: "docs/a",
  markdown,
  conversionError: null,
  tabs,
  github: null,
  columns: {},
  tableKeys: [],
  diff: null,
  updatedAt: "2026-11-20T04:00:00Z",
  ...overrides,
});

const handlers = (document: Record<string, unknown>) => [
  http.get(DOCUMENT, () => HttpResponse.json(document)),
  http.get(REFS, () =>
    HttpResponse.json({
      git: true,
      defaultRef: "main",
      branches: [{ name: "main", commit: "8b1d4e0" }],
      tags: [],
      commits: [
        {
          commit: "8b1d4e0",
          date: "2026-11-20T13:00:00+09:00",
          subject: "docs: 変更",
        },
      ],
    }),
  ),
  http.get(SETTINGS, () =>
    HttpResponse.json({
      settingsPath: "/home/u/.config/project-index/settings.yaml",
      sources: [
        {
          id: "sample",
          config: ["/home/u/repo/sample/project-index.yaml"],
          enabled: true,
          scope: { read: ["/home/u/repo/sample/**"], write: null },
          status: "serving",
        },
      ],
    }),
  ),
];

const meta = {
  title: "Docs/DocViewScreen",
  component: DocViewScreen,
} satisfies Meta<typeof DocViewScreen>;

export default meta;
type Story = StoryObj<typeof meta>;

/** 本文と列の多い表。画面が広いときは本文と表がサイドバーを除いた画面の幅まで広がる */
export const WideTable: Story = {
  parameters: { msw: handlers(documentResponse()) },
};

/** 文書の無いタブを選んだとき */
export const EmptyTab: Story = {
  parameters: { msw: handlers(documentResponse()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByText("規約"));
    await expect(
      await canvas.findByText("規約の文書はありません"),
    ).toBeInTheDocument();
  },
};

/** 本文を変換できなかったとき */
export const ConversionError: Story = {
  parameters: {
    msw: handlers(
      documentResponse({
        markdown: null,
        conversionError: {
          reason: "timeout",
          kind: "screen",
          script: "scripts/convert.py",
          detail: "制限時間を超えました",
        },
      }),
    ),
  },
};

/** 検索から除外される文書（`search_exclude` に該当）がサイドバーにあるとき */
export const ExcludedDocs: Story = {
  parameters: {
    msw: handlers(
      documentResponse({
        tabs: [
          {
            ...tabs[0],
            items: [
              {
                ...tabs[0].items[0],
                items: [
                  page("文書の画面", "docs/a"),
                  { ...page("旧設定画面", "docs/b"), excluded: true },
                  page("見つからない画面", "docs/c"),
                ],
              },
            ],
          },
          tabs[1],
        ],
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByRole("img", { name: "検索から除外" }),
    ).toBeInTheDocument();
  },
};

const group = (title: string, items: ReturnType<typeof page>[]) => ({
  kind: "group" as const,
  title,
  path: null,
  items,
  change: null,
});

/** group が 3 つある配信元（開いている文書は 1 つ目の group にある） */
const groupedTabs = [
  {
    title: "設計書",
    active: true,
    items: [
      group("画面", [
        page("文書の画面", "docs/a"),
        page("設定画面", "docs/b"),
        page("見つからない画面", "docs/c"),
      ]),
      group("インターフェース定義", [
        page("文書の取得", "docs/d"),
        page("メタデータの取得", "docs/e"),
      ]),
      group("モジュール構成", [
        page("doc-sidebar.tsx", "docs/f"),
        page("doc-view-screen.tsx", "docs/g"),
      ]),
    ],
  },
  tabs[1],
];

/** サイドバーの開閉と幅を story の間で持ち越さないように、描く前に指定して描いた後に戻す */
const withSidebar =
  (state: { sidebarOpen?: boolean; sidebarWidth?: number }) => () => {
    usePreferencesStore.setState(state);
    return () =>
      usePreferencesStore.setState({
        sidebarOpen: true,
        sidebarWidth: SIDEBAR_WIDTH.initial,
      });
  };

/** group を見出しで折りたたむ。開いている文書を含む group だけ開いて始まる */
export const NavGroups: Story = {
  beforeEach: withSidebar({}),
  parameters: { msw: handlers(documentResponse({ tabs: groupedTabs })) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const opened = await canvas.findByRole("button", { name: "画面" });
    await expect(opened).toHaveAttribute("aria-expanded", "true");
    const closed = canvas.getByRole("button", { name: "インターフェース定義" });
    await expect(closed).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(closed);
    await expect(await canvas.findByText("文書の取得")).toBeInTheDocument();
  },
};

/** サイドバーを閉じたとき。本文がサイドバーの幅だけ広がり、左上に開くボタンが出る */
export const SidebarClosed: Story = {
  beforeEach: withSidebar({ sidebarOpen: false }),
  parameters: { msw: handlers(documentResponse({ tabs: groupedTabs })) },
};

/** サイドバーの幅を最大まで広げたとき */
export const SidebarWide: Story = {
  beforeEach: withSidebar({ sidebarWidth: SIDEBAR_WIDTH.max }),
  parameters: { msw: handlers(documentResponse({ tabs: groupedTabs })) },
};

/** 画面幅 48rem 未満の文書の一覧のドロワー。group の折りたたみはドロワーの中でも同じ */
export const NarrowDrawer: Story = {
  beforeEach: withSidebar({}),
  parameters: {
    msw: handlers(documentResponse({ tabs: groupedTabs })),
    viewport: { defaultViewport: "mobile1" },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      await canvas.findByRole("button", { name: "文書の一覧を開く" }),
    );
  },
};

/** 差分を確認しているとき。開いている文書を含まない group も、変化のマーカーを持つ page があれば開いて始まる */
export const ChangedInOtherGroup: Story = {
  beforeEach: withSidebar({}),
  parameters: {
    msw: handlers(
      documentResponse({
        tabs: [
          {
            ...groupedTabs[0],
            items: groupedTabs[0].items.map((item) =>
              item.title === "インターフェース定義"
                ? {
                    ...item,
                    items: [
                      { ...page("文書の取得", "docs/d"), change: "modified" },
                      page("メタデータの取得", "docs/e"),
                    ],
                  }
                : item,
            ),
          },
          tabs[1],
        ],
        diff: { base: "8b1d4e0", change: null, changedItems: [] },
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByRole("button", { name: "インターフェース定義" }),
    ).toHaveAttribute("aria-expanded", "true");
    await expect(
      canvas.getByRole("button", { name: "モジュール構成" }),
    ).toHaveAttribute("aria-expanded", "false");
  },
};

/** nav の group を 4 段まで入れ子にした配信元。入れ子の段の数は配信元の設定（`nav`）で決まり、画面は段の数を制限しない */
export const DeepNestedGroups: Story = {
  beforeEach: withSidebar({}),
  parameters: {
    msw: handlers(
      documentResponse({
        path: "docs/d",
        tabs: [
          {
            ...groupedTabs[0],
            items: [
              group("画面", [page("文書の画面", "docs/a")]),
              {
                ...group("設計書", []),
                items: [
                  {
                    ...group("サーバー", []),
                    items: [
                      {
                        ...group("画面の API", [
                          page("文書の取得", "docs/d"),
                          page("メタデータの取得", "docs/e"),
                        ]),
                      },
                      page("起動", "docs/f"),
                    ],
                  },
                ],
              },
            ],
          },
          tabs[1],
        ],
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByRole("button", { name: "画面の API" }),
    ).toHaveAttribute("aria-expanded", "true");
  },
};

const PREVIEW = "*/_api/sources/:source/preview";

const LONG_TITLE = "文書の画面から Markdown と YAML の文書の本文を編集して編集中のパネルからまとめて直コミットする決まり";

/** 規約の文書（YAML）の本文の項目。変換が目印を付けたブロックごとに描く */
const ruleBlocks = (long = false): DocEdit["blocks"] => {
  const description = long
    ? "文書の画面から、Markdown の文書とスキーマを持つ YAML の文書の本文を、種類ごとの個別の対応を持たずにスキーマの型から選んだ部品で編集し、編集中のパネルからまとめて直コミットする決まりを定め、本文を編集するときに参照する。"
    : "文書の画面から本文を編集する決まりを定め、本文を編集するときに参照する。";
  const overview = "文書の画面から、どの種類の文書の本文も編集できる。\n編集した内容は編集中のパネルからまとめてコミットする。";
  const rows = [
    { word: "直す", replacement: "修正" },
    { word: long ? "書き込みの API から直コミットできる種類の一覧に無い" : "消す", replacement: long ? "write_api_kinds に無い" : "削除" },
  ];
  const overviewPath = long ? "items[edit-document-body-from-doc-view-screen].body" : "items[overview].body";
  const overviewLabel = long ? "文書の画面から本文を編集してまとめて直コミットする決まりの概要" : "概要";
  return [
    { path: "description", label: "説明", type: "string", value: description, markdown: description },
    {
      path: "status",
      label: "状態",
      type: "enum",
      value: "current",
      options: ["current", "draft", "deprecated"],
      markdown: "状態: current",
    },
    {
      path: overviewPath,
      label: overviewLabel,
      type: "markdown",
      value: overview,
      markdown: `## ${overviewLabel}\n\n${overview}`,
    },
    {
      path: "rows",
      label: "単語の対応表",
      type: "table",
      columns: ["word", "replacement"],
      value: rows,
      markdown: ["## 単語の対応表", "", "| word | replacement |", "| --- | --- |", ...rows.map((row) => `| ${row.word} | ${row.replacement} |`)].join("\n"),
    },
  ];
};

const ruleSource = [
  "id: rule-sample",
  "kind: rule",
  "name: 文書の編集",
  "description: 文書の画面から本文を編集する決まりを定め、本文を編集するときに参照する。",
  "status: current",
  "items:",
  "  - id: overview",
  "    name: 概要",
  "    body: |-",
  "      文書の画面から、どの種類の文書の本文も編集できる。",
  "      編集した内容は編集中のパネルからまとめてコミットする。",
  "rows:",
  "  - word: 直す",
  "    replacement: 修正",
  "  - word: 消す",
  "    replacement: 削除",
  "",
].join("\n");

const ruleEditOf = (long = false): DocEdit => ({
  docId: "docs-a",
  kind: "rule",
  filePath: "docs/a.yaml",
  version: "a1b2c3",
  baseCommit: "1111111",
  language: "yaml",
  source: ruleSource,
  blocks: ruleBlocks(long),
  titleBlock: { path: "name", label: "名前", type: "string", value: long ? LONG_TITLE : "文書の編集", markdown: "" },
});

const ruleEdit = ruleEditOf();

const ruleDoc = (edit: DocEdit = ruleEdit, title = "文書の編集") =>
  documentResponse({
    path: "docs/a",
    markdown: [`# ${title}`, "", ...edit.blocks.map((block) => block.markdown), ""].join("\n\n"),
    tabs: [{ ...tabs[0], items: [{ ...tabs[0].items[0], items: [page(title, "docs/a"), page("設定画面", "docs/b")] }] }, tabs[1]],
    edit,
  });

/** 書き換えた YAML の概要と表だけを Markdown にするモックの変換 */
const previewOf = (content: string): string => {
  const lines = content.split("\n");
  const description = lines.find((line) => line.startsWith("description:"))?.slice("description:".length).trim() ?? "";
  const start = lines.findIndex((line) => line.trim() === "body: |-");
  const body = [];
  for (const line of start < 0 ? [] : lines.slice(start + 1)) {
    if (!line.startsWith("      ")) break;
    body.push(line.trim());
  }
  return [description, "", "## 概要", "", body.join("\n"), ""].join("\n");
};

const editHandlers = (document: Record<string, unknown>) => [
  ...handlers(document),
  http.post(PREVIEW, async ({ request }) => {
    const { content } = (await request.json()) as { content: string };
    return HttpResponse.json({ markdown: previewOf(content) });
  }),
];

/** ガイドの文書（Markdown）。ファイル全体の編集だけを持つ */
const guideDoc = documentResponse({
  path: "docs/a",
  markdown: "# 画面で参照する\n\n## 手順\n\n1. 文書を開く\n2. 編集を押す\n",
  edit: {
    docId: "guide",
    kind: "guide",
    filePath: "docs/guide.md",
    version: "d4e5f6",
    baseCommit: "1111111",
    language: "markdown",
    source: "# 画面で参照する\n\n## 手順\n\n1. 文書を開く\n2. 編集を押す\n",
    blocks: [],
    titleBlock: null,
  } satisfies DocEdit,
});

/** 編集中の変更をストアに入れてから描く */
const withEdits = (items: PendingEdit[]) => () => {
  usePendingEditsStore.setState({ bySource: { sample: items }, baseCommitBySource: { sample: "8b1d4e0" } });
  return () => usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
};

const bodyEdit = (path: string, label: string, before: string, value: string, docPath = "docs/a"): PendingEdit => ({
  key: `body:${docPath}:${path}`,
  kind: "body",
  op: "update",
  docId: docPath,
  docKind: "rule",
  expectedVersion: "a1b2c3",
  docPath,
  values: { [path]: value },
  before: { [path]: before },
  label: `${label}（${docPath}）`,
});

const bodyEdits: PendingEdit[] = [
  bodyEdit("description", "説明", "文書の画面から本文を編集する決まりを定め、本文を編集するときに参照する。", ""),
  bodyEdit("@file", "ファイル全体", "# 画面で参照する", "# 画面で参照する（変更後）", "docs/b"),
];

/** 編集できる文書には、タイトルの横に編集のボタンが出る */
export const EditButton: Story = {
  parameters: { msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(await canvas.findByRole("button", { name: "編集" })).toBeInTheDocument();
  },
};

/** 書き込みの API が書き込めない種類（`write_api_kinds` に無い・`body: false`・SQLite の行）は、編集のボタンを出さない */
export const NotEditable: Story = {
  parameters: { msw: editHandlers({ ...ruleDoc(), edit: null }) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await canvas.findByRole("heading", { level: 1 });
    await expect(canvas.queryByRole("button", { name: "編集" })).toBeNull();
  },
};

/** 表示した場所で修正。描いた本文のブロックごとに編集のボタンを出す */
export const EditFields: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc()) },
};

/** 短い文字列のブロックを押して、その場の入力欄で修正しているとき。書き換えはその場で編集中の変更に入る */
export const EditFieldsInline: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "説明 を編集" }));
    await userEvent.type(canvas.getByRole("textbox", { name: "説明" }), "（追記）");
    await expect(await canvas.findByRole("button", { name: "編集中 1 件" })).toBeInTheDocument();
  },
};

/** タイトルの横の編集のボタンを押して、タイトルをその場で修正しているとき */
export const EditFieldsTitle: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "名前 を編集" }));
    await expect(canvas.getByRole("textbox", { name: "名前" })).toHaveValue("文書の編集");
  },
};

/** 表のブロックを押して、セルを直接修正しているとき（見出しは描いたまま） */
export const EditFieldsTable: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "単語の対応表 を編集" }));
  },
};

/** Markdown の文字列の項目を、画面の横のパネルでエディタとプレビューを並べて編集する */
export const EditMarkdownField: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "概要 を編集" }));
    const body = within(canvasElement.ownerDocument.body);
    await expect(await body.findByRole("dialog", { name: "概要 の編集" })).toBeInTheDocument();
  },
};

/** 長いタイトル・項目のパス・項目名・表のセルのとき（表示した場所で修正） */
export const EditFieldsLongValues: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc(ruleEditOf(true), LONG_TITLE)) },
};

/** 長い項目名と項目のパスの、横のパネル */
export const EditMarkdownFieldLongValues: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: editHandlers(ruleDoc(ruleEditOf(true), LONG_TITLE)) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      await canvas.findByRole("button", { name: "文書の画面から本文を編集してまとめて直コミットする決まりの概要 を編集" }),
    );
  },
};

/** YAML の文書のファイル全体の編集。エディタとプレビューを左右に並べ、プレビューは書き換えを変換して描く */
export const EditWholeFileYaml: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=file", msw: editHandlers(ruleDoc()) },
};

/** ファイル全体を書き換えたとき。書き換えはその場で編集中の変更に入り、プレビューが追従する */
export const EditWholeFileChanged: Story = {
  beforeEach: withEdits([bodyEdit("@file", "ファイル全体", ruleSource, ruleSource.replace("どの種類の文書の本文も編集できる。", "Markdown と YAML の文書の本文を編集できる。"))]),
  parameters: { initialPath: "/sample/docs/a?edit=file", msw: editHandlers(ruleDoc()) },
};

/** ファイル全体の編集で YAML として解析できない書き換えをしたとき。エディタの上に理由を出し、プレビューは最後に変換できた内容のまま */
export const EditWholeFileInvalid: Story = {
  beforeEach: withEdits([bodyEdit("@file", "ファイル全体", ruleSource, ruleSource.replace("  - word: 消す", "\t- word: 消す"))]),
  parameters: { initialPath: "/sample/docs/a?edit=file", msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(await canvas.findByRole("alert")).toHaveTextContent("YAML として解析できません");
  },
};

/** 長いタイトルとパスの、ファイル全体の編集 */
export const EditWholeFileLongValues: Story = {
  beforeEach: withEdits([]),
  parameters: {
    initialPath: "/sample/docs/a?edit=file",
    msw: editHandlers({
      ...ruleDoc(ruleEditOf(true), LONG_TITLE),
      bodyPath: "docs/rule/rule-edit-document-body-from-doc-view-screen-and-commit-from-pending-panel.yaml",
    }),
  },
};

/** Markdown の文書はファイル全体の編集だけを持つ */
export const EditMarkdownDoc: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=file", msw: editHandlers(guideDoc) },
};

/** 文書の画面で編集中のパネルを開いたとき。本文の変更をメタデータの変更と同じパネルに並べる */
export const PendingPanelOnDocView: Story = {
  beforeEach: withEdits(bodyEdits),
  parameters: { msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "編集中 2 件" }));
  },
};

/** 長いラベルの本文の変更を並べた編集中のパネル */
export const PendingPanelLongLabels: Story = {
  beforeEach: withEdits([
    bodyEdit(
      "items[edit-document-body-from-doc-view-screen].body",
      "文書の画面から本文を編集してまとめて直コミットする決まりの概要",
      "文書の画面から、どの種類の文書の本文も編集できる。",
      "文書の画面から、Markdown と YAML の文書の本文を編集できる。",
      "docs/rule/rule-edit-document-body-from-doc-view-screen-and-commit-from-pending-panel.yaml",
    ),
  ]),
  parameters: { msw: editHandlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "編集中 1 件" }));
  },
};

/** 本文の変更が検査に合格しないとき。差分確認で、違反した項目のパスと理由を変更に出す */
export const BodyEditInvalid: Story = {
  beforeEach: withEdits(bodyEdits),
  parameters: {
    msw: [
      ...editHandlers(ruleDoc()),
      http.post(COMMITS, () =>
        HttpResponse.json(
          {
            type: "about:blank",
            status: 422,
            title: "EditsRejectedError",
            detail: "検査に合格しませんでした",
            nextSteps: [],
            errors: [{ key: "body:docs/a:description", path: "description", reason: "空にできません" }],
          },
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "編集中 2 件" }));
    const body = within(canvasElement.ownerDocument.body);
    await userEvent.click(await body.findByRole("button", { name: "差分確認" }));
  },
};

/** 収まらない長さの名前の page と group の見出し（折り返さず末尾を「…」で省略する） */
const longNameTabs = [
  {
    title: "設計書",
    active: true,
    items: [
      group(
        "開発ドキュメントサーバー / 画面の API / 文書の取得と検索とリビジョンの一覧",
        [
          page("文書の画面", "docs/a"),
          page(
            "画面 / 文書の画面 / search-dialog.tsx（配信元を横断して文書を単語で探すダイアログ）",
            "docs/b",
          ),
          page("見つからない画面", "docs/c"),
        ],
      ),
    ],
  },
  tabs[1],
];

/** サイドバーの名前が長いとき（既定の幅） */
export const LongNames: Story = {
  beforeEach: withSidebar({}),
  parameters: { msw: handlers(documentResponse({ tabs: longNameTabs })) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const link = await canvas.findByRole("link", {
      name: /search-dialog\.tsx/,
    });
    await expect(link.querySelector("[title]")).toHaveAttribute(
      "title",
      "画面 / 文書の画面 / search-dialog.tsx（配信元を横断して文書を単語で探すダイアログ）",
    );
  },
};

/** サイドバーの名前が長く、幅を最大まで広げたとき */
export const LongNamesWide: Story = {
  beforeEach: withSidebar({ sidebarWidth: SIDEBAR_WIDTH.max }),
  parameters: { msw: handlers(documentResponse({ tabs: longNameTabs })) },
};

/** 画面の高さを超える本文（本文の領域の中だけがスクロールし、画面全体はスクロールしない） */
export const LongBody: Story = {
  beforeEach: withSidebar({}),
  parameters: {
    msw: handlers(
      documentResponse({
        markdown: [
          markdown,
          ...Array.from({ length: 12 }, (_, i) =>
            [
              `## 節 ${i + 1}`,
              "",
              "本文の領域の中でスクロールし、トップバー・種類のタブ・サイドバーは画面に残る。",
              "",
            ].join("\n"),
          ),
        ].join("\n"),
      }),
    ),
  },
};
