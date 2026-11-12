import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";

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
