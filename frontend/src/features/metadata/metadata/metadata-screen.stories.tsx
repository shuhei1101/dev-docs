import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";

import {
  MetadataScreen,
  type MetadataResponse,
  type PendingEdit,
} from "@/features/metadata/metadata/metadata-screen";

const METADATA = "*/_api/sources/sample/metadata";
const COMMITS = "*/_api/sources/sample/commits";

const metadata: MetadataResponse = {
  source: "sample",
  branch: "develop",
  kinds: [
    {
      id: "terms",
      title: "用語集",
      served: true,
      editable: true,
      columns: [
        { key: "name", label: "用語" },
        { key: "aliases", label: "別名" },
        { key: "description", label: "説明" },
      ],
      rows: [
        {
          id: "source",
          version: "a1b2c3",
          values: {
            name: "配信元",
            aliases: "source",
            description: "project-index.yaml を持つフォルダ 1 つ",
          },
        },
        {
          id: "old-name",
          version: "b2c3d4",
          values: {
            name: "旧称",
            aliases: "",
            description: "使用しない呼び名",
          },
        },
      ],
    },
    {
      id: "aliases",
      title: "エイリアス",
      served: true,
      editable: true,
      columns: [
        { key: "name", label: "名前" },
        { key: "aliases", label: "別名" },
        { key: "path", label: "文書" },
      ],
      rows: [
        {
          id: "n1",
          docPath: "docs/note/n1.yaml",
          version: "c3d4e5",
          values: {
            name: "直コミット",
            aliases: "direct commit",
            path: "docs/note/n1.yaml",
          },
        },
      ],
    },
    {
      id: "tags",
      title: "タグ",
      served: true,
      editable: true,
      columns: [
        { key: "path", label: "文書" },
        { key: "tags", label: "タグ" },
      ],
      rows: [
        {
          id: "n1",
          docPath: "docs/note/n1.yaml",
          version: "c3d4e5",
          values: { path: "docs/note/n1.yaml", tags: "topic:a" },
        },
      ],
    },
    {
      id: "rules",
      title: "rule-inject の索引",
      served: true,
      editable: true,
      columns: [
        { key: "rule", label: "規約" },
        { key: "paths", label: "適用するパス" },
        { key: "tools", label: "ツール" },
        { key: "args", label: "引数" },
      ],
      rows: [
        {
          id: "0",
          version: "d4e5f6",
          values: {
            rule: "docs/rule/a.yaml",
            paths: "**/*.py",
            tools: "",
            args: "",
          },
        },
        {
          id: "1",
          version: "d4e5f6",
          values: {
            rule: "docs/rule/b.yaml",
            paths: "docs/**",
            tools: "write_docs",
            args: "",
          },
        },
      ],
    },
    {
      id: "config",
      title: "配信元の設定",
      served: true,
      editable: false,
      columns: [
        { key: "id", label: "種類" },
        { key: "paths", label: "パス" },
        { key: "direct", label: "直コミット" },
      ],
      rows: [
        {
          id: "note",
          version: "e5f6a7",
          values: { id: "note", paths: "docs/note/*.yaml", direct: "✓" },
        },
        {
          id: "rule",
          version: "e5f6a7",
          values: { id: "rule", paths: "docs/rule/*.yaml", direct: "" },
        },
      ],
    },
    {
      id: "files",
      title: "管理用の YAML",
      served: true,
      editable: true,
      columns: [
        { key: "records", label: "行" },
        { key: "path", label: "ファイル" },
        { key: "description", label: "概要" },
      ],
      rows: [
        {
          id: "src/app.py",
          version: "f6a7b8",
          values: {
            records: "src",
            path: "src/app.py",
            description: "アプリの組み立て",
          },
        },
      ],
    },
  ],
};

const indexNotServed: MetadataResponse = {
  ...metadata,
  kinds: metadata.kinds.map((kind) =>
    kind.id === "rules"
      ? {
          ...kind,
          served: false,
          rows: [],
          hint: "- id: rules\n  paths: [rules.yaml]\n  schema: rule-inject の索引のスキーマ",
        }
      : kind,
  ),
};

const edits: PendingEdit[] = [
  {
    key: "tags:n1:update",
    kind: "tags",
    rowId: "n1",
    op: "update",
    label: "タグ: docs/note/n1.yaml",
    before: "topic:a",
    after: "topic:a, topic:b",
  },
  {
    key: "terms:new:add",
    kind: "terms",
    rowId: "new",
    op: "add",
    label: "用語集: 種類",
  },
  {
    key: "terms:old-name:delete",
    kind: "terms",
    rowId: "old-name",
    op: "delete",
    label: "用語集: 旧称",
  },
];

const listed = (body: MetadataResponse) =>
  http.get(METADATA, () => HttpResponse.json(body));

const problem = (status: number, body: Record<string, unknown>) =>
  http.post(COMMITS, () =>
    HttpResponse.json(
      { type: "about:blank", status, nextSteps: [], ...body },
      { status, headers: { "Content-Type": "application/problem+json" } },
    ),
  );

const meta = {
  title: "Metadata/MetadataScreen",
  component: MetadataScreen,
  args: { source: "sample" },
} satisfies Meta<typeof MetadataScreen>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  parameters: { msw: [listed(metadata)] },
};

export const KindNotServed: Story = {
  parameters: { msw: [listed(indexNotServed)] },
};

export const PendingEdits: Story = {
  args: { initialEdits: edits, initialPanelOpen: true },
  parameters: { msw: [listed(metadata)] },
};

export const DryRun: Story = {
  args: { initialEdits: edits, initialPanelOpen: true },
  parameters: {
    msw: [
      listed(metadata),
      http.post(COMMITS, () =>
        HttpResponse.json({
          diffs: [
            {
              key: "tags:n1:update",
              diff: "-   - topic:a\n+   - topic:a\n+   - topic:b",
            },
            { key: "terms:new:add", diff: "+ - name: 種類" },
            { key: "terms:old-name:delete", diff: "- - name: 旧称" },
          ],
        }),
      ),
    ],
  },
};

export const SendConfirm: Story = {
  args: {
    initialEdits: edits,
    initialPanelOpen: true,
    initialConfirmOpen: true,
  },
  parameters: { msw: [listed(metadata)] },
};

export const ValidationFailed: Story = {
  args: { initialEdits: edits, initialPanelOpen: true },
  parameters: {
    msw: [
      listed(metadata),
      problem(422, {
        title: "検査に合格しない修正があります",
        errors: [
          {
            key: "terms:new:add",
            message:
              "terms[2].name: 空にできません。用語の名前を入力してください",
          },
        ],
      }),
    ],
  },
};

export const VersionMismatch: Story = {
  args: { initialEdits: edits.slice(0, 1), initialPanelOpen: true },
  parameters: {
    msw: [
      listed(metadata),
      problem(409, {
        title: "他の変更と食い違う修正があります",
        errors: [
          {
            key: "tags:n1:update",
            message:
              "docs/note/n1.yaml は他の変更で変わりました（今のバージョン 9f8e7d）。一覧を読み直してから修正し直してください",
          },
        ],
      }),
    ],
  },
};

export const NotPermitted: Story = {
  args: { initialEdits: edits.slice(0, 1), initialPanelOpen: true },
  parameters: {
    msw: [
      listed(metadata),
      problem(403, {
        title: "直コミットを許可していない種類があります",
        errors: [
          {
            key: "tags:n1:update",
            message:
              "種類 note は直コミットを許可していません。project-index の端末の設定の sources[].direct_commit.write_api_kinds に記載してください",
          },
        ],
      }),
    ],
  },
};

export const RemoteUnreachable: Story = {
  args: { initialEdits: edits.slice(0, 1), initialPanelOpen: true },
  parameters: {
    msw: [
      listed(metadata),
      problem(502, {
        title: "リモートに接続できませんでした",
        detail: "git fetch に失敗しました。リモートの URL を確認してください",
      }),
    ],
  },
};
