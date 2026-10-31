import type {
  DocumentResponse,
  NavItem,
  RefsResponse,
  ScreenSearchResult,
  SettingsSourceRow,
  SettingsSourcesView,
} from "@/shared/api/generated/model";

export const TABLE_KEY = "sample:items";

export const DOC_MARKDOWN = [
  "# 文書 1",
  "",
  "## 概要",
  "",
  "文書 1 の本文です。一覧のページングは先頭から数えます。",
  "",
  "## 項目",
  "",
  "### 項目の表",
  "",
  "<!-- table: data +columns -->",
  "",
  "| キー | 名称 | 備考 |",
  "| --- | --- | --- |",
  "| k1 | 名称 1 | 備考 1 |",
  "| k2 | 名称 2 | 備考 2 |",
  "",
  "<!-- /table -->",
  "",
  "## 関連",
  "",
  "別の文書は [文書 2](./doc-2) を読みます。外部は [公式](https://example.com/) を見ます。",
  "",
].join("\n");

const page = (
  title: string,
  path: string,
  change: NavItem["change"] = null,
): NavItem => ({ kind: "page", title, path, items: [], change });

const group = (title: string, items: NavItem[]): NavItem => ({
  kind: "group",
  title,
  path: null,
  items,
  change: null,
});

export const DOC_PATHS = ["docs/doc-1", "docs/doc-2"] as const;

export const refsResponse = (
  overrides: Partial<RefsResponse> = {},
): RefsResponse => ({
  git: true,
  defaultRef: "develop",
  branches: [
    { name: "develop", commit: "8b1d4e0" },
    { name: "feat/frontend/react-spa", commit: "7c0aa11" },
  ],
  tags: [{ name: "v0.1.0", commit: "3f2a9c1" }],
  commits: [
    {
      commit: "8b1d4e0",
      date: "2026-10-26T11:30:00+09:00",
      subject: "docs: 文書を追加",
    },
    {
      commit: "7c0aa11",
      date: "2026-10-25T11:30:00+09:00",
      subject: "docs: 規約を修正",
    },
  ],
  ...overrides,
});

export const documentResponse = (
  overrides: Partial<DocumentResponse> = {},
): DocumentResponse => ({
  source: "sample",
  ref: "develop",
  path: "docs/doc-1",
  bodyPath: null,
  markdown: DOC_MARKDOWN,
  conversionError: null,
  tabs: [
    {
      title: "規約",
      active: true,
      items: [
        group("設計", [
          page("文書 1", "docs/doc-1"),
          page("文書 2", "docs/doc-2"),
        ]),
      ],
    },
    { title: "補足", active: false, items: [] },
  ],
  github: { repository: "shuhei1101/dev-docs", issueLabels: ["docs"] },
  columns: {},
  tableKeys: [TABLE_KEY],
  diff: null,
  updatedAt: "2026-10-26T05:40:00Z",
  ...overrides,
});

export const settingsSource = (
  id: string,
  overrides: Partial<SettingsSourceRow> = {},
): SettingsSourceRow => ({
  id,
  config: [`/home/me/${id}/dev-docs.yaml`],
  enabled: true,
  scope: { read: ["/home/me/**"], write: null },
  status: "serving",
  errors: [],
  configVersion: null,
  ...overrides,
});

export const settingsView = (
  sources: SettingsSourceRow[] = [
    settingsSource("sample"),
    settingsSource("knowledge", { scope: { read: ["/home/me/**"], write: ["/home/me/knowledge/**"] } }),
  ],
): SettingsSourcesView => ({
  settingsPath: "/home/me/.config/dev-docs/settings.yaml",
  sources,
});

export const searchResult = (
  overrides: Partial<ScreenSearchResult> = {},
): ScreenSearchResult => ({
  totalCount: 2,
  items: [
    {
      path: "docs/doc-1",
      name: "文書 1",
      snippets: ["…一覧のページングは先頭から数えます…"],
    },
    {
      path: "docs/doc-2",
      name: "文書 2",
      snippets: ["…ページングの説明…"],
    },
  ],
  ...overrides,
});

export type SeedComment = {
  id: string;
  path: string;
  docTitle: string;
  headings: string[];
  quote: string;
  prefix?: string;
  suffix?: string;
  body: string;
  selected?: boolean;
};

/** 溜めたコメントを、ブラウザのタブの sessionStorage に置いた状態にする(`page.addInitScript` に渡す値) */
export const seededComments = (rows: SeedComment[]): string =>
  JSON.stringify({
    state: {
      comments: rows.map((row) => ({
        id: row.id,
        docId: `sample@develop:${row.path}`,
        source: "sample",
        ref: "develop",
        path: row.path,
        docTitle: row.docTitle,
        headings: row.headings,
        quote: row.quote,
        prefix: row.prefix ?? "",
        suffix: row.suffix ?? "",
        body: row.body,
        selected: row.selected ?? true,
        createdAt: "2026-10-26T05:40:00.000Z",
      })),
    },
    version: 1,
  });

export const TWO_COMMENTS: [SeedComment, SeedComment] = [
  {
    id: "c1",
    path: "docs/doc-1",
    docTitle: "文書 1",
    headings: ["概要"],
    quote: "一覧のページングは先頭から数えます",
    body: "ページングの数え方を確認したい",
  },
  {
    id: "c2",
    path: "docs/doc-2",
    docTitle: "文書 2",
    headings: [],
    quote: "文書 2 の冒頭",
    body: "冒頭の説明が足りない",
  },
];
