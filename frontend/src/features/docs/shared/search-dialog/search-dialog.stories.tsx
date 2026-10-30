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
  },
  {
    path: "docs/design/paging",
    name: "ページング",
    snippets: ["…一覧のページングは…"],
  },
];

const meta = {
  title: "Docs/SearchDialog",
  component: SearchDialog,
  args: {
    open: true,
    onOpenChange: fn(),
    source: "sample",
    ref: "develop",
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
            detail: "検索する語が正しくありません",
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
