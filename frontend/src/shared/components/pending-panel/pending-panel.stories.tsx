import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";
import { userEvent, within } from "storybook/test";

import { PendingPanel } from "@/shared/components/pending-panel/pending-panel";
import { type PendingEdit, usePendingEditsStore } from "@/shared/stores/pending-edits-store";

const COMMITS = "*/_api/sources/sample/commits";
const PROBLEM_HEADERS = { "Content-Type": "application/problem+json" };

const tagEdit: PendingEdit = {
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
};

const termAdd: PendingEdit = {
  key: "terms:kind:add",
  kind: "terms",
  op: "add",
  docId: "kind",
  docKind: "terms",
  expectedVersion: null,
  docPath: null,
  values: { name: "種類", description: "文書の行の ID" },
  before: {},
  label: "用語集: 種類",
};

const termDelete: PendingEdit = {
  key: "terms:old-name:delete",
  kind: "terms",
  op: "delete",
  docId: "old-name",
  docKind: "terms",
  expectedVersion: "b2c3d4",
  docPath: "glossary.yaml",
  values: {},
  before: {},
  label: "用語集: 旧名",
};

type BodyEdit = { path: string; label: string; before: string; value: string; docPath?: string };

const bodyEdit = ({ path, label, before, value, docPath = "notes/n1.yaml" }: BodyEdit): PendingEdit => ({
  key: `body:${docPath}:${path}`,
  kind: "body",
  op: "update",
  docId: docPath,
  docKind: "note",
  expectedVersion: "c3d4e5",
  docPath,
  values: { [path]: value },
  before: { [path]: before },
  label: `${label}（${docPath}）`,
});

const summaryEdit = bodyEdit({ path: "summary", label: "概要", before: "概要", value: "修正後の概要" });
const fileEdit = bodyEdit({
  path: "@file",
  label: "ファイル全体",
  before: "title: n2\nsummary: 概要\n",
  value: "title: n2\nsummary: 修正後\n",
  docPath: "notes/n2.yaml",
});

/** 配信元 sample の編集中の変更を入れる */
const withEdits = (edits: PendingEdit[]) => () => {
  usePendingEditsStore.setState({
    bySource: { sample: edits },
    baseCommitBySource: edits.length === 0 ? {} : { sample: "00b7c00" },
  });
};

const meta = {
  title: "Layout/PendingPanel",
  component: PendingPanel,
  args: { source: "sample", branch: "develop", open: true, onOpenChange: () => {}, onLocate: () => {} },
} satisfies Meta<typeof PendingPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

/** メタデータの変更 3 件（タグの修正・用語の追加・用語の削除） */
export const MetadataEdits: Story = { beforeEach: withEdits([tagEdit, termAdd, termDelete]) };

/** 文書の本文の変更（項目のパスの修正・ファイル全体の編集）とメタデータの変更が並ぶ */
export const BodyEdits: Story = { beforeEach: withEdits([tagEdit, summaryEdit, fileEdit]) };

/** 差分確認を押した後。変更ごとに差分を出す */
export const DryRunDiff: Story = {
  beforeEach: withEdits([tagEdit, summaryEdit]),
  parameters: {
    msw: {
      handlers: [
        http.post(COMMITS, () =>
          HttpResponse.json({
            applied: false,
            results: [
              { key: tagEdit.key, status: "updated", version: "v2", diff: "   tags:\n     - name: topic:a\n+    - name: topic:b" },
              { key: summaryEdit.key, status: "updated", version: "v2", diff: "-summary: 概要\n+summary: 修正後の概要" },
            ],
            commit: null,
          }),
        ),
      ],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement.ownerDocument.body);
    await userEvent.click(await canvas.findByRole("button", { name: "差分確認" }));
  },
};

/** 差分確認で本文の変更が検査に合格しない。その変更の行に違反した項目のパスと理由を出す */
export const BodyEditInvalid: Story = {
  beforeEach: withEdits([summaryEdit]),
  parameters: {
    msw: {
      handlers: [
        http.post(COMMITS, () =>
          HttpResponse.json(
            {
              type: "about:blank",
              title: "EditsRejectedError",
              status: 422,
              detail: "検査に合格しませんでした",
              errors: [{ key: summaryEdit.key, path: "summary", reason: "1 文字以上の文字列にしてください" }],
            },
            { status: 422, headers: PROBLEM_HEADERS },
          ),
        ),
      ],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement.ownerDocument.body);
    await userEvent.click(await canvas.findByRole("button", { name: "差分確認" }));
  },
};

/** コミットで衝突し、修正を残したブランチ・PR の URL・衝突した理由を出す */
export const Conflict: Story = {
  beforeEach: withEdits([tagEdit, summaryEdit]),
  parameters: {
    msw: {
      handlers: [
        http.post(COMMITS, () =>
          HttpResponse.json({
            applied: false,
            results: [],
            commit: null,
            conflict: {
              branch: "project-index/conflict/20261127-101500-00b7c00",
              baseCommit: "00b7c00",
              reasons: [{ key: summaryEdit.key, reason: "summary はほかの変更で変わっています" }],
              script: { exitCode: 0, timedOut: false, prUrl: "https://github.com/o/r/pull/9", stderr: "" },
            },
          }),
        ),
      ],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement.ownerDocument.body);
    await userEvent.click(await canvas.findByRole("button", { name: "コミット" }));
    await userEvent.type(await canvas.findByRole("textbox", { name: "コミットの説明" }), "概要を修正する");
    const dialog = await canvas.findByRole("dialog", { name: /コミット/ });
    await userEvent.click(within(dialog).getByRole("button", { name: "コミット" }));
  },
};

/** 編集中の変更が 0 件 */
export const Empty: Story = { beforeEach: withEdits([]) };

/** 長い項目の名前と文書のパスの本文の変更。行を折り返し、パネルの幅を超えない */
export const LongLabels: Story = {
  beforeEach: withEdits([
    bodyEdit({
      path: "#items[書き込みの-api-から直コミットできる種類].body",
      label: "書き込みの API から直コミットできる種類 の 本文",
      before: "短い",
      value: "書き込みの API から直コミットできる種類の一覧に無い種類は、文書の画面に編集のボタンを出さない",
      docPath: "docs/interface/very/long/folder/name/for/the/document/IF-155-10.yaml",
    }),
  ]),
};

/** 幅 48rem 未満の場所で、下から出す */
export const Narrow: Story = {
  beforeEach: withEdits([tagEdit, summaryEdit]),
  globals: { viewport: { value: "mobile1", isRotated: false } },
};
