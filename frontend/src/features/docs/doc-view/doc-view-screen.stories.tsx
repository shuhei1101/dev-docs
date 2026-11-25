import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";
import { expect, userEvent, within } from "storybook/test";

import { DocViewScreen } from "@/features/docs/doc-view/doc-view-screen";
import type { DocEdit } from "@/features/docs/doc-view/edit";
import { type PendingEdit, usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
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

/** 規約の文書（YAML）の本文。表示した場所で修正できる項目を持つ */
const ruleEdit: DocEdit = {
  editable: true,
  language: "yaml",
  kind: "rule",
  version: "a1b2c3",
  source: [
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
  ].join("\n"),
  blocks: [
    { path: "name", label: "名前", type: "string", value: "文書の編集" },
    {
      path: "description",
      label: "説明",
      type: "string",
      value: "文書の画面から本文を編集する決まりを定め、本文を編集するときに参照する。",
    },
    { path: "status", label: "状態", type: "enum", value: "current", options: ["current", "draft", "deprecated"] },
    {
      path: "items[overview].body",
      label: "概要",
      type: "markdown",
      value: "文書の画面から、どの種類の文書の本文も編集できる。\n編集した内容は編集中のパネルからまとめてコミットする。",
    },
    {
      path: "rows",
      label: "単語の対応表",
      type: "table",
      columns: ["word", "replacement"],
      value: [
        { word: "直す", replacement: "修正" },
        { word: "消す", replacement: "削除" },
      ],
    },
  ],
};

const ruleMarkdown = ["# 文書の編集", "", "## 概要", "", "文書の画面から、どの種類の文書の本文も編集できる。", ""].join("\n");

const ruleDoc = (edit: DocEdit = ruleEdit) => documentResponse({ path: "docs/a", markdown: ruleMarkdown, edit });

/** ガイドの文書（Markdown）。ファイル全体の編集だけを持つ */
const guideDoc = documentResponse({
  path: "docs/a",
  markdown: "# 画面で参照する\n\n## 手順\n\n1. 文書を開く\n2. 編集を押す\n",
  edit: {
    editable: true,
    language: "markdown",
    kind: "guide",
    version: "d4e5f6",
    source: "# 画面で参照する\n\n## 手順\n\n1. 文書を開く\n2. 編集を押す\n",
    blocks: [],
  } satisfies DocEdit,
});

/** 編集中の変更をストアに入れてから描く */
const withEdits = (items: PendingEdit[]) => () => {
  usePendingEditsStore.setState({ bySource: { sample: items }, baseCommitBySource: { sample: "8b1d4e0" } });
  return () => usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
};

const bodyEdits: PendingEdit[] = [
  {
    key: "body:sample:docs/a:name",
    kind: "body",
    op: "update",
    docId: "sample:docs/a",
    docKind: "rule",
    expectedVersion: "a1b2c3",
    docPath: "docs/a",
    values: { name: "文書の本文の編集" },
    before: { name: "文書の編集" },
    label: "名前（docs/a）",
  },
  {
    key: "body:sample:docs/b:@file",
    kind: "body",
    op: "update",
    docId: "sample:docs/b",
    docKind: "guide",
    expectedVersion: "d4e5f6",
    docPath: "docs/b",
    values: { "@file": "# 画面で参照する（変更後）" },
    before: { "@file": "# 画面で参照する" },
    label: "ファイル全体（docs/b）",
  },
];

/** 編集できる文書には、タイトルの横に編集のボタンが出る */
export const EditButton: Story = {
  parameters: { msw: handlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(await canvas.findByRole("button", { name: "編集" })).toBeInTheDocument();
  },
};

/** 書き込みの API が書き込めない種類（`write_api_kinds` に無い・`body: false`・SQLite の行）は、編集のボタンを出さない */
export const NotEditable: Story = {
  parameters: { msw: handlers(ruleDoc({ ...ruleEdit, editable: false })) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await canvas.findByRole("heading", { level: 1 });
    await expect(canvas.queryByRole("button", { name: "編集" })).toBeNull();
  },
};

/** YAML の文書の表示した場所での修正。項目ごとにスキーマの型から選んだ部品で修正する */
export const EditFields: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: handlers(ruleDoc()) },
};

/** 短い文字列の項目をその場で修正しているとき */
export const EditFieldsInline: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: handlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "名前 を編集" }));
    await expect(canvas.getByRole("textbox", { name: "名前" })).toHaveValue("文書の編集");
  },
};

/** Markdown の文字列の項目を、画面の横のパネルでエディタとプレビューを並べて編集する */
export const EditMarkdownField: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=fields", msw: handlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "概要 を編集" }));
    const body = within(canvasElement.ownerDocument.body);
    await expect(await body.findByRole("dialog", { name: "概要 の編集" })).toBeInTheDocument();
  },
};

/** YAML の文書のファイル全体の編集。エディタとプレビューを左右に並べる */
export const EditWholeFileYaml: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=file", msw: handlers(ruleDoc()) },
};

/** ファイル全体の編集で YAML として解析できない書き換えをしたとき。エディタの上に理由を出し、適用できない */
export const EditWholeFileInvalid: Story = {
  beforeEach: withEdits([]),
  parameters: {
    initialPath: "/sample/docs/a?edit=file",
    msw: handlers(ruleDoc({ ...ruleEdit, source: ruleEdit.source.replace("  - word: 消す", "\t- word: 消す") })),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(await canvas.findByRole("alert")).toHaveTextContent("YAML として解析できません");
  },
};

/** Markdown の文書はファイル全体の編集だけを持つ */
export const EditMarkdownDoc: Story = {
  beforeEach: withEdits([]),
  parameters: { initialPath: "/sample/docs/a?edit=file", msw: handlers(guideDoc) },
};

/** 文書の画面で編集中のパネルを開いたとき。本文の変更をメタデータの変更と同じパネルに並べる */
export const PendingPanelOnDocView: Story = {
  beforeEach: withEdits(bodyEdits),
  parameters: { msw: handlers(ruleDoc()) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole("button", { name: "編集中 2 件" }));
  },
};

/** 本文の変更が検査に合格しないとき。差分確認で、違反した項目のパスと理由を変更に出す */
export const BodyEditInvalid: Story = {
  beforeEach: withEdits(bodyEdits),
  parameters: {
    msw: [
      ...handlers(ruleDoc()),
      http.post(COMMITS, () =>
        HttpResponse.json(
          {
            type: "about:blank",
            status: 422,
            title: "EditsRejectedError",
            detail: "検査に合格しませんでした",
            nextSteps: [],
            errors: [{ key: "body:sample:docs/a:name", path: "name", reason: "空にできません" }],
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
