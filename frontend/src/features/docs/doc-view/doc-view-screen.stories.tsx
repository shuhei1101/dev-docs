import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";
import { expect, userEvent, within } from "storybook/test";

import { DocViewScreen } from "@/features/docs/doc-view/doc-view-screen";

const DOCUMENT = "*/_api/sources/:source/docs/*";
const REFS = "*/_api/sources/:source/refs";
const SETTINGS = "*/_api/settings/sources";

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
