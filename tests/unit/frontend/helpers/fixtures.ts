export const page = (
  title: string,
  path: string,
  change: string | null = null,
) => ({
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
    {
      commit: "8b1d4e0",
      date: "2026-10-26T11:30:00+09:00",
      subject: "docs: 変更",
    },
    {
      commit: "7c0aa11",
      date: "2026-10-25T11:30:00+09:00",
      subject: "docs: 追加",
    },
  ],
  ...overrides,
});

export const settingsSource = (
  id: string,
  overrides: Record<string, unknown> = {},
) => ({
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
    {
      title: "設計書",
      active: true,
      items: [group("設計", [page("A", "a.md"), page("B", "b.md")])],
    },
    { title: "規約", active: false, items: [] },
  ],
  github: null,
  columns: {},
  tableKeys: [],
  diff: null,
  updatedAt: "2026-10-26T14:40:00Z",
  ...overrides,
});

export const problem = (
  status: number,
  extra: Record<string, unknown> = {},
) => ({
  type: "urn:dev-docs:error:Error",
  title: "Error",
  status,
  detail: "失敗しました",
  nextSteps: [],
  ...extra,
});

export const PROBLEM_HEADERS = { "Content-Type": "application/problem+json" };
