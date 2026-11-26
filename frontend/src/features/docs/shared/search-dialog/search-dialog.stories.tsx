import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, delay, http } from "msw";
import { expect, fn, userEvent, within } from "storybook/test";

import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";

const SEARCH = "/_api/sources/:source/search";

const items = [
  {
    path: "docs/design/search",
    name: "検索の設計",
    snippets: ["…ページングの扱いは…"],
    matchCount: 2,
  },
  {
    path: "docs/design/paging",
    name: "ページング",
    snippets: ["…一覧のページングは…"],
    matchCount: 9,
  },
];

/** 30 件の結果（名前の順と一致した行の数の順が食い違い、名前の順で最後の文書の一致が最も多い） */
const manyItems = Array.from({ length: 30 }, (_, index) => ({
  path: `docs/design/page-${String(index + 1).padStart(2, "0")}`,
  name: `ページングの設計 ${String(index + 1).padStart(2, "0")}${index === 29 ? "（一覧・検索の結果・メタデータの表で共通のページングの決まり）" : ""}`,
  snippets: [
    `…${index + 1} 件目の文書のページングは、一覧の末尾の行から次の行を読み込む…`,
  ],
  matchCount: index === 29 ? 42 : ((index * 7) % 13) + 1,
}));

const meta = {
  title: "Docs/SearchDialog",
  component: SearchDialog,
  args: {
    open: true,
    onOpenChange: fn(),
    source: "sample",
    ref: "develop",
    sources: ["sample", "notes"],
    onResultSelect: fn(),
  },
} satisfies Meta<typeof SearchDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

const typeQuery = async ({ canvasElement }: { canvasElement: HTMLElement }) => {
  const input = await within(canvasElement.ownerDocument.body).findByRole(
    "combobox",
  );
  await userEvent.type(input, "ページング");
};

export const Empty: Story = {};

export const Results: Story = {
  parameters: {
    msw: [http.get(SEARCH, () => HttpResponse.json({ totalCount: 2, items }))],
  },
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await expect(
      await body.findByText("2 件（リビジョン develop）"),
    ).toBeInTheDocument();
  },
};

/** 検索から除外される文書があり、既定の結果から除いたとき */
export const ExcludedCount: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, () =>
        HttpResponse.json({ totalCount: 2, items, excludedCount: 1 }),
      ),
    ],
  },
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await expect(
      await body.findByText("2 件（リビジョン develop）・検索から除外 1 件"),
    ).toBeInTheDocument();
  },
};

/** 一致した文書が全て検索から除外される文書だったとき */
export const OnlyExcludedMatched: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, () =>
        HttpResponse.json({ totalCount: 0, items: [], excludedCount: 1 }),
      ),
    ],
  },
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await expect(
      await body.findByText(
        "該当する文書はありません。配信元の設定で検索から除外した文書を含めると 1 件あります。",
      ),
    ).toBeInTheDocument();
  },
};

/** 検索から除外した文書も含めて検索したとき */
export const IncludeExcluded: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, ({ request }) =>
        new URL(request.url).searchParams.get("include_excluded") === "true"
          ? HttpResponse.json({
              totalCount: 3,
              items: [
                ...items,
                {
                  path: "docs/design/old-paging",
                  name: "旧ページング",
                  snippets: ["…ページングの以前の扱いは…"],
                  excluded: true,
                },
              ],
            })
          : HttpResponse.json({ totalCount: 2, items, excludedCount: 1 }),
      ),
    ],
  },
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await userEvent.click(
      body.getByRole("switch", {
        name: "配信元の設定で検索から除外した文書も含める",
      }),
    );
    await expect(await body.findByText("検索から除外")).toBeInTheDocument();
  },
};

export const NoResults: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, () => HttpResponse.json({ totalCount: 0, items: [] })),
    ],
  },
  play: typeQuery,
};

export const Loading: Story = {
  args: { ref: undefined },
  parameters: {
    msw: [
      http.get(SEARCH, async () => {
        await delay("infinite");
        return HttpResponse.json({ totalCount: 0, items: [] });
      }),
    ],
  },
  play: typeQuery,
};

export const Failed: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, () =>
        HttpResponse.json(
          {
            type: "urn:dev-docs:error:InvalidArgumentError",
            title: "InvalidArgumentError",
            status: 400,
            detail: "検索する単語が正しくありません",
            nextSteps: [],
          },
          {
            status: 400,
            headers: { "Content-Type": "application/problem+json" },
          },
        ),
      ),
    ],
  },
  play: typeQuery,
};

export const NonGitSource: Story = {
  args: { source: "notes", ref: undefined },
  parameters: {
    msw: [http.get(SEARCH, () => HttpResponse.json({ totalCount: 2, items }))],
  },
  play: typeQuery,
};

export const ProjectIndexUnreachable: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, () =>
        HttpResponse.json(
          {
            type: "about:blank",
            title: "Service Unavailable",
            status: 503,
            detail:
              "project-index（http://127.0.0.1:8786）に接続できませんでした。接続を拒否されました（Connection refused）",
            nextSteps: [],
            projectIndex: {
              address: "http://127.0.0.1:8786",
              reason: "接続を拒否されました（Connection refused）",
            },
          },
          {
            status: 503,
            headers: { "Content-Type": "application/problem+json" },
          },
        ),
      ),
    ],
  },
  play: typeQuery,
};

/** 一覧の高さを超える 30 件に一致したとき（一覧の中でスクロールする） */
export const ManyResults: Story = {
  parameters: {
    msw: [
      http.get(SEARCH, () =>
        HttpResponse.json({ totalCount: 30, items: manyItems }),
      ),
    ],
  },
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await expect(
      await body.findByText("30 件（リビジョン develop）"),
    ).toBeInTheDocument();
  },
};

/** 並び順を名前の順に切り替えたとき */
export const SortedByName: Story = {
  parameters: ManyResults.parameters,
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await body.findByText("30 件（リビジョン develop）");
    await userEvent.click(body.getByRole("radio", { name: "名前" }));
    await expect(body.getByRole("radio", { name: "名前" })).toBeChecked();
  },
};

const notesItems = [
  {
    path: "notes/paging-memo",
    name: "ページングのメモ",
    snippets: ["…ページングの試し書き…"],
    matchCount: 4,
  },
];

/** 検索の範囲を全ての配信元に切り替えたとき（行に配信元の名前を出す） */
export const AllSources: Story = {
  args: { sources: ["sample", "notes"] },
  parameters: {
    msw: [
      http.get(SEARCH, ({ params }) =>
        HttpResponse.json(
          params.source === "notes"
            ? { totalCount: 1, items: notesItems }
            : { totalCount: 2, items },
        ),
      ),
    ],
  },
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await userEvent.click(body.getByRole("radio", { name: "全ての配信元" }));
    await expect(await body.findByText("3 件")).toBeInTheDocument();
  },
};

/** 全ての配信元の検索で、配信していない配信元があったとき（問い合わせずに理由を並べる） */
export const AllSourcesPartialFailure: Story = {
  args: {
    sources: ["sample", "notes"],
    unavailable: [
      {
        source: "broken",
        reason:
          "project-index が起動時の検証で除外しました。 documents[0] paths は必須です",
      },
    ],
  },
  parameters: AllSources.parameters,
  play: async (context) => {
    await typeQuery(context);
    const body = within(context.canvasElement.ownerDocument.body);
    await userEvent.click(body.getByRole("radio", { name: "全ての配信元" }));
    await expect(
      await body.findByRole("list", { name: "検索できなかった配信元" }),
    ).toBeInTheDocument();
  },
};
