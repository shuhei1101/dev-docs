import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, delay, http } from "msw";
import { userEvent, within } from "storybook/test";

import { MetadataScreen } from "@/features/metadata/metadata/metadata-screen";
import { type PendingEdit, usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
import type { MetadataColumn, MetadataKind, MetadataResponse } from "@/shared/api/generated/model";

const METADATA = "*/_api/sources/sample/metadata";
const COMMITS = "*/_api/sources/sample/commits";
const SETTINGS = "*/_api/settings/sources";
const METADATA_PATH = "/sample/_metadata";
const PANEL_PATH = "/sample/_metadata?panel=edits";

const column = (key: string, label: string, overrides: Partial<MetadataColumn> = {}): MetadataColumn => ({
  key,
  label,
  type: "text",
  editable: true,
  ...overrides,
});

const kind = (overrides: Partial<MetadataKind> & Pick<MetadataKind, "id" | "title">): MetadataKind => ({
  served: true,
  hint: null,
  columns: [],
  canAdd: false,
  canDelete: false,
  createKind: null,
  rows: [],
  ...overrides,
});

const metadata: MetadataResponse = {
  source: "sample",
  branch: "develop",
  baseCommit: "00b7c00",
  kinds: [
    kind({
      id: "terms",
      title: "用語集",
      columns: [column("name", "用語"), column("aliases", "別名", { type: "list" }), column("description", "説明")],
      canAdd: true,
      canDelete: true,
      createKind: "terms",
      rows: [
        {
          id: "source",
          docKind: "terms",
          docPath: "glossary.yaml",
          version: "a1b2c3",
          editable: true,
          values: { name: "配信元", aliases: ["source"], description: "project-index.yaml を持つフォルダ 1 つ" },
        },
        {
          id: "old-name",
          docKind: "terms",
          docPath: "glossary.yaml",
          version: "b2c3d4",
          editable: true,
          values: { name: "旧称", aliases: [], description: "使用しない呼び名" },
        },
      ],
    }),
    kind({
      id: "aliases",
      title: "エイリアス",
      columns: [
        column("name", "名前"),
        column("aliases", "別名", { type: "list" }),
        column("path", "文書", { editable: false }),
      ],
      rows: [
        {
          id: "n1",
          docKind: "note",
          docPath: "docs/note/n1.yaml",
          version: "c3d4e5",
          editable: true,
          values: { name: "直コミット", aliases: ["direct commit"], path: "docs/note/n1.yaml" },
        },
      ],
    }),
    kind({
      id: "tags",
      title: "タグ",
      columns: [column("path", "文書", { editable: false }), column("tags", "タグ", { type: "list" })],
      rows: [
        {
          id: "n1",
          docKind: "note",
          docPath: "docs/note/n1.yaml",
          version: "c3d4e5",
          editable: true,
          values: { path: "docs/note/n1.yaml", tags: ["topic:a"] },
        },
      ],
    }),
    kind({
      id: "rules",
      title: "rule-inject の索引",
      columns: [
        column("rule", "規約"),
        column("paths", "適用するパス", { type: "list" }),
        column("tools", "ツール", { type: "list" }),
        column("args", "引数", { editable: false }),
      ],
      canDelete: true,
      createKind: "rule_index",
      rows: [
        {
          id: "r1",
          docKind: "rule_index",
          docPath: "rules.yaml",
          version: "d4e5f6",
          editable: false,
          values: { rule: "docs/rule/a.yaml", paths: ["**/*.py"], tools: [], args: "" },
        },
      ],
    }),
    kind({
      id: "config",
      title: "配信元の設定",
      columns: [
        column("id", "種類", { editable: false }),
        column("paths", "パス", { type: "list", editable: false }),
        column("direct_commit", "直コミット", { editable: false }),
      ],
      rows: [
        { id: "note", docKind: null, docPath: null, version: null, editable: false, values: { id: "note", paths: ["docs/note/*.yaml"], direct_commit: "✓" } },
        { id: "rule_index", docKind: null, docPath: null, version: null, editable: false, values: { id: "rule_index", paths: ["rules.yaml"], direct_commit: "" } },
      ],
    }),
    kind({
      id: "files",
      title: "管理用の YAML",
      columns: [
        column("records", "行", { editable: false }),
        column("path", "ファイル", { editable: false }),
        column("description", "概要"),
      ],
      rows: [
        {
          id: "f1",
          docKind: "files",
          docPath: "src/app.py",
          version: "f6a7b8",
          editable: true,
          values: { records: "files", path: "src/app.py", description: "アプリの組み立て" },
        },
      ],
    }),
  ],
};

const indexNotServed: MetadataResponse = {
  ...metadata,
  kinds: metadata.kinds.map((item) =>
    item.id === "rules"
      ? { ...item, served: false, rows: [], hint: "documents:\n  - id: rule_index\n    paths: [rules.yaml]\n    records: rules" }
      : item,
  ),
};

const edits: PendingEdit[] = [
  {
    key: "tags:n1:update",
    kind: "tags",
    op: "update",
    docId: "n1",
    docKind: "note",
    expectedVersion: "c3d4e5",
    docPath: "notes/n1.yaml",
    values: { tags: ["topic:a", "topic:b"] },
    before: { tags: ["topic:a"] },
    label: "タグ: n1",
  },
  {
    key: "terms:kind:add",
    kind: "terms",
    op: "add",
    docId: "kind",
    docKind: "terms",
    expectedVersion: null,
    docPath: null,
    values: { name: "種類" },
    before: {},
    label: "用語集: 種類",
  },
  {
    key: "terms:old-name:delete",
    kind: "terms",
    op: "delete",
    docId: "old-name",
    docKind: "terms",
    expectedVersion: "b2c3d4",
    docPath: "glossary.yaml",
    values: {},
    before: {},
    label: "用語集: 旧称",
  },
];

const listed = (body: MetadataResponse) => [
  http.get(METADATA, () => HttpResponse.json(body)),
  http.get(SETTINGS, () => HttpResponse.json({ settingsPath: "/pi/settings.yaml", sources: [], version: "v1" })),
];

const problem = (status: number, body: Record<string, unknown>) =>
  http.post(COMMITS, () =>
    HttpResponse.json(
      { type: "about:blank", status, detail: "", nextSteps: [], ...body },
      { status, headers: { "Content-Type": "application/problem+json" } },
    ),
  );

/** 編集中の変更をストアに入れてから描く */
const withEdits = (items: PendingEdit[]) => () => {
  usePendingEditsStore.setState({ bySource: { sample: items } });
  return {};
};

/** パネルのコミットから確認のダイアログを経てコミットする */
const commitFromPanel = async ({ canvasElement }: { canvasElement: HTMLElement }) => {
  const body = within(canvasElement.ownerDocument.body);
  await userEvent.click(await body.findByRole("button", { name: "コミット" }));
  const dialog = within(await body.findByRole("dialog", { name: "コミットしますか？" }));
  await userEvent.type(dialog.getByRole("textbox", { name: "コミットの説明" }), "用語とタグを修正する");
  await userEvent.click(dialog.getByRole("button", { name: "コミット" }));
};

const meta = {
  title: "Metadata/MetadataScreen",
  component: MetadataScreen,
  args: { source: "sample" },
  parameters: { initialPath: METADATA_PATH },
  loaders: [withEdits([])],
} satisfies Meta<typeof MetadataScreen>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  parameters: { msw: listed(metadata) },
};

export const KindNotServed: Story = {
  parameters: { msw: listed(indexNotServed), initialPath: `${METADATA_PATH}?tab=rules` },
};

export const ReadOnlyConfig: Story = {
  parameters: { msw: listed(metadata), initialPath: `${METADATA_PATH}?tab=config` },
};

export const PendingEdits: Story = {
  loaders: [withEdits(edits)],
  parameters: { msw: listed(metadata), initialPath: PANEL_PATH },
};

export const DryRun: Story = {
  loaders: [withEdits(edits)],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      http.post(COMMITS, () =>
        HttpResponse.json({
          applied: false,
          results: [
            { key: "tags:n1:update", status: "updated", version: "x1", diff: "-   - topic:a\n+   - topic:a\n+   - topic:b" },
            { key: "terms:kind:add", status: "created", version: "x2", diff: "+ - name: 種類" },
            { key: "terms:old-name:delete", status: "deleted", version: null, diff: "- - name: 旧称" },
          ],
          commit: null,
        }),
      ),
    ],
  },
  play: async ({ canvasElement }) => {
    const body = within(canvasElement.ownerDocument.body);
    await userEvent.click(await body.findByRole("button", { name: "差分確認" }));
  },
};

export const ValidationFailed: Story = {
  loaders: [withEdits(edits)],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      problem(422, {
        title: "EditsRejectedError",
        detail: "検査に合格しませんでした",
        errors: [{ key: "terms:kind:add", path: "description", reason: "空にできません" }],
      }),
    ],
  },
  play: commitFromPanel,
};

const CONFLICT_BRANCH = "project-index/conflict/20261123-103000-0a1b2c3";

/** 衝突して修正をブランチに残した 200 の応答 */
const conflicted = (script: Record<string, unknown> | null) =>
  http.post(COMMITS, () =>
    HttpResponse.json({
      applied: false,
      results: [],
      commit: null,
      conflict: {
        branch: CONFLICT_BRANCH,
        baseCommit: "00b7c00a9a63ce55977e39adde09ecf434f02a36",
        reasons: [{ key: "tags:n1:update", reason: "n1 のタグが、編集を始めた後のほかの変更で書き換わっています" }],
        script,
      },
    }),
  );

export const OtherItemChanged: Story = {
  loaders: [withEdits(edits.slice(0, 1))],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      http.post(COMMITS, () =>
        HttpResponse.json({
          applied: true,
          results: [{ key: "tags:n1:update", status: "updated", version: "e5f6a7", diff: "+   - topic:b" }],
          commit: { sha: "1b2c3d4e5f", branch: "develop" },
        }),
      ),
    ],
  },
  play: commitFromPanel,
};

export const ConflictKeptOnBranch: Story = {
  loaders: [withEdits(edits.slice(0, 2))],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      conflicted({ exitCode: 0, timedOut: false, prUrl: "https://github.com/shuhei1101/sample/pull/42", stderr: "" }),
    ],
  },
  play: commitFromPanel,
};

export const ConflictScriptFailed: Story = {
  loaders: [withEdits(edits.slice(0, 1))],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      conflicted({ exitCode: 1, timedOut: false, prUrl: null, stderr: "gh: authentication required" }),
    ],
  },
  play: commitFromPanel,
};

export const ConflictScriptNotConfigured: Story = {
  loaders: [withEdits(edits.slice(0, 1))],
  parameters: { initialPath: PANEL_PATH, msw: [...listed(metadata), conflicted(null)] },
  play: commitFromPanel,
};

export const BaseCommitUnusable: Story = {
  loaders: [withEdits(edits.slice(0, 1))],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      problem(409, {
        title: "BaseCommitUnusableError",
        detail: "編集を始めたときのコミット 00b7c00 が develop の履歴にありません",
        nextSteps: [],
      }),
    ],
  },
  play: commitFromPanel,
};

export const NotPermitted: Story = {
  loaders: [withEdits(edits.slice(0, 1))],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      problem(403, {
        title: "EditsRejectedError",
        detail: "直コミットを許可していない種類があります",
        nextSteps: ["project-index の端末の設定の sources[].direct_commit.write_api_kinds に種類を追加してください。"],
        errors: [{ key: "tags:n1:update", reason: "note は直コミットを許可していません" }],
      }),
    ],
  },
  play: commitFromPanel,
};

export const RemoteUnreachable: Story = {
  loaders: [withEdits(edits.slice(0, 1))],
  parameters: {
    initialPath: PANEL_PATH,
    msw: [
      ...listed(metadata),
      problem(502, { title: "EditsRejectedError", detail: "project-index が 502 を返却しました。git fetch に失敗しました" }),
    ],
  },
  play: commitFromPanel,
};

export const Loading: Story = {
  parameters: {
    msw: [
      http.get(METADATA, async () => {
        await delay("infinite");
        return HttpResponse.json(metadata);
      }),
    ],
  },
};

export const ProjectIndexUnreachable: Story = {
  parameters: {
    msw: [
      http.get(METADATA, () =>
        HttpResponse.json(
          {
            type: "about:blank",
            title: "ProjectIndexUnreachableError",
            status: 503,
            detail: "project-index（http://127.0.0.1:8786）に接続できませんでした。",
            nextSteps: [],
            projectIndex: {
              address: "http://127.0.0.1:8786",
              reason: "接続を拒否されました（Connection refused）",
              kind: "unreachable",
            },
          },
          { status: 503, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    ],
  },
};

export const EmptyKind: Story = {
  parameters: {
    msw: listed({
      ...metadata,
      kinds: metadata.kinds.map((item) => (item.id === "terms" ? { ...item, rows: [] } : item)),
    }),
  },
};
