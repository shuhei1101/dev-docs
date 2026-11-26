export const page = (title: string, path: string, change: string | null = null) => ({
  kind: "page" as const,
  title,
  path,
  items: [],
  change,
});

export const group = (title: string, items: ReturnType<typeof page>[]) => ({
  kind: "group" as const,
  title,
  path: null,
  items,
  change: null,
});

export const refsResponse = (overrides: Record<string, unknown> = {}) => ({
  git: true,
  defaultRef: "main",
  branches: [{ name: "main", commit: "8b1d4e0" }],
  tags: [{ name: "v0.1.0", commit: "3f2a9c1" }],
  commits: [
    { commit: "8b1d4e0", date: "2026-10-26T11:30:00+09:00", subject: "docs: 変更" },
    { commit: "7c0aa11", date: "2026-10-25T11:30:00+09:00", subject: "docs: 追加" },
  ],
  ...overrides,
});

export const settingsSource = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  config: [`/home/me/${id}/dev-docs.yaml`],
  enabled: true,
  scope: { read: ["/home/me/**"], write: null },
  status: "serving",
  errors: [],
  configVersion: null,
  ...overrides,
});

export const settingsView = (sources: ReturnType<typeof settingsSource>[]) => ({
  settingsPath: "/home/me/.config/dev-docs/settings.yaml",
  sources,
});

export const documentResponse = (overrides: Record<string, unknown> = {}) => ({
  source: "s",
  ref: "main",
  path: "a.md",
  markdown: "# A\n\n本文\n",
  conversionError: null,
  tabs: [
    { title: "設計書", active: true, items: [group("設計", [page("A", "a.md"), page("B", "b.md")])] },
    { title: "規約", active: false, items: [] },
  ],
  github: null,
  columns: {},
  tableKeys: [],
  diff: null,
  updatedAt: "2026-10-26T14:40:00Z",
  ...overrides,
});

export const problem = (status: number, extra: Record<string, unknown> = {}) => ({
  type: "urn:dev-docs:error:Error",
  title: "Error",
  status,
  detail: "失敗しました",
  nextSteps: [],
  ...extra,
});

export const PROBLEM_HEADERS = { "Content-Type": "application/problem+json" };

export const metadataColumn = (key: string, label: string, overrides: Record<string, unknown> = {}) => ({
  key,
  label,
  type: "text",
  editable: true,
  ...overrides,
});

export const metadataRow = (id: string, values: Record<string, string | string[]>, overrides: Record<string, unknown> = {}) => ({
  id,
  docKind: "note",
  docPath: `notes/${id}.yaml`,
  version: `v-${id}`,
  editable: true,
  values,
  ...overrides,
});

export const metadataKind = (id: string, title: string, overrides: Record<string, unknown> = {}) => ({
  id,
  title,
  served: true,
  hint: null,
  columns: [],
  canAdd: false,
  canDelete: false,
  createKind: null,
  rows: [],
  ...overrides,
});

/** 6 種類のメタデータ（用語 1 件・タグ 1 件） */
export const metadataResponse = () => ({
  source: "sample",
  branch: "develop",
  baseCommit: "aaa1111",
  kinds: [
    metadataKind("terms", "用語集", {
      columns: [metadataColumn("name", "用語"), metadataColumn("aliases", "別名", { type: "list" }), metadataColumn("description", "説明")],
      canAdd: true,
      canDelete: true,
      createKind: "terms",
      rows: [metadataRow("source", { name: "配信元", aliases: ["source"], description: "フォルダ" }, { docKind: "terms", docPath: "glossary.yaml" })],
    }),
    metadataKind("aliases", "エイリアス", {
      columns: [metadataColumn("name", "名前"), metadataColumn("aliases", "別名", { type: "list" }), metadataColumn("path", "文書", { editable: false })],
    }),
    metadataKind("tags", "タグ", {
      columns: [metadataColumn("path", "文書", { editable: false }), metadataColumn("tags", "タグ", { type: "list" })],
      rows: [metadataRow("n1", { path: "notes/n1.yaml", tags: ["topic:a"] })],
    }),
    metadataKind("rules", "rule-inject の索引"),
    metadataKind("config", "配信元の設定"),
    metadataKind("files", "管理用の YAML"),
  ],
});

export const editBlock = (
  path: string,
  overrides: Record<string, unknown> = {},
) => ({
  path,
  label: path,
  type: "string",
  markdown: `**${path}**: 値`,
  value: "値",
  options: null,
  columns: null,
  ...overrides,
});

export const docEdit = (overrides: Record<string, unknown> = {}) => ({
  docId: "n1",
  kind: "note",
  filePath: "notes/n1.yaml",
  version: "v-n1",
  baseCommit: "ccc3333",
  language: "yaml",
  source: "title: n1\nsummary: 概要\n",
  blocks: [
    editBlock("summary", {
      label: "概要",
      markdown: "**概要**: 概要",
      value: "概要",
    }),
    editBlock("status", {
      label: "状態",
      type: "enum",
      markdown: "**状態**: draft",
      value: "draft",
      options: ["draft", "current"],
    }),
    editBlock("#items[i1].body", {
      label: "i1 の 本文",
      type: "markdown",
      markdown: "**本文**",
      value: "**本文**",
    }),
    editBlock("rows", {
      label: "置き換え",
      type: "table",
      markdown: "| word | replacement |\n| --- | --- |\n| a | b |\n| c | d |",
      value: [
        { word: "a", replacement: "b" },
        { word: "c", replacement: "d" },
      ],
      columns: ["word", "replacement"],
    }),
  ],
  titleBlock: editBlock("title", {
    label: "タイトル",
    markdown: "# n1",
    value: "n1",
  }),
  ...overrides,
});
