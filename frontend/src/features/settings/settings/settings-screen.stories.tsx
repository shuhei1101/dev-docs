import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";
import { expect, userEvent, within } from "storybook/test";

import { SettingsScreen } from "@/features/settings/settings/settings-screen";

const SETTINGS = "*/_api/settings/sources";

const sources = [
  {
    id: "sample",
    config: ["/home/u/repo/sample/project-index.yaml"],
    enabled: true,
    scope: { read: ["/home/u/repo/sample/**"], write: null },
    status: "serving",
  },
  {
    id: "broken",
    config: ["/home/u/repo/broken/project-index.yaml"],
    enabled: true,
    scope: { read: ["/home/u/repo/broken/**"], write: null },
    status: "not_served",
    errors: [{ path: "documents[0].paths", reason: "必須のキーが無い" }],
  },
  {
    id: "legacy",
    config: ["/home/u/repo/legacy/project-index.yaml"],
    enabled: true,
    scope: { read: ["/home/u/repo/legacy/**"], write: null },
    status: "serving",
    configVersion: { config: "2", server: "3" },
  },
];

const sourcesWithOutsideReadDisabled = [
  { ...sources[0] },
  {
    id: "private-notes",
    config: ["/home/u/repo/private-notes/project-index.yaml"],
    enabled: true,
    scope: { read: ["/home/u/repo/private-notes/**"], write: null },
    status: "serving",
    outsideRead: false,
  },
];

const listed = (rows: typeof sourcesWithOutsideReadDisabled) =>
  http.get(SETTINGS, () =>
    HttpResponse.json({
      settingsPath: "/home/u/.config/project-index/settings.yaml",
      sources: rows,
    }),
  );

const conflict = () =>
  HttpResponse.json(
    {
      type: "about:blank",
      title: "Conflict",
      status: 409,
      detail: "端末の設定はほかの書き換えで変わっています",
      nextSteps: [],
      current: "b2c3d4",
    },
    { status: 409, headers: { "Content-Type": "application/problem+json" } },
  );

const meta = {
  title: "Settings/SettingsScreen",
  component: SettingsScreen,
} satisfies Meta<typeof SettingsScreen>;

export default meta;
type Story = StoryObj<typeof meta>;

export const SourceNotServed: Story = {
  parameters: {
    msw: [
      http.get(SETTINGS, () =>
        HttpResponse.json({
          settingsPath: "/home/u/.config/project-index/settings.yaml",
          sources,
        }),
      ),
    ],
  },
};

export const ProjectIndexUnreachable: Story = {
  parameters: {
    msw: [
      http.get(SETTINGS, () =>
        HttpResponse.json(
          {
            type: "about:blank",
            title: "Service Unavailable",
            status: 503,
            detail: "project-index に接続できませんでした",
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
};

export const OutsideReadDisabled: Story = {
  parameters: { msw: [listed(sourcesWithOutsideReadDisabled)] },
};

export const EditOutsideRead: Story = {
  parameters: { msw: [listed(sourcesWithOutsideReadDisabled)] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      await canvas.findByRole("button", { name: "private-notes を編集" }),
    );
    const body = within(canvasElement.ownerDocument.body);
    await expect(
      await body.findByRole("switch", {
        name: "範囲の外から参照できるようにする",
      }),
    ).not.toBeChecked();
  },
};

export const SaveConflict: Story = {
  parameters: {
    msw: [listed(sourcesWithOutsideReadDisabled), http.put(SETTINGS, conflict)],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      await canvas.findByRole("button", { name: "sample を編集" }),
    );
    const body = within(canvasElement.ownerDocument.body);
    await userEvent.click(await body.findByRole("button", { name: "保存" }));
    await expect(
      await body.findByText("ほかの変更があったため保存できませんでした"),
    ).toBeInTheDocument();
  },
};

export const DeleteConflict: Story = {
  parameters: {
    msw: [listed(sourcesWithOutsideReadDisabled), http.put(SETTINGS, conflict)],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      await canvas.findByRole("button", { name: "private-notes を削除" }),
    );
    const body = within(canvasElement.ownerDocument.body);
    await userEvent.click(await body.findByRole("button", { name: "削除" }));
    await expect(
      await body.findByText(/ほかの変更があったため削除できませんでした/),
    ).toBeInTheDocument();
  },
};
