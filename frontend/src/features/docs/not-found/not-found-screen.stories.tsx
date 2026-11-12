import type { Meta, StoryObj } from "@storybook/react-vite";
import { HttpResponse, http } from "msw";

import { NotFoundScreen } from "@/features/docs/not-found/not-found-screen";

const SETTINGS = "*/_api/settings/sources";

const meta = {
  title: "Docs/NotFoundScreen",
  component: NotFoundScreen,
  parameters: {
    msw: [
      http.get(SETTINGS, () =>
        HttpResponse.json({
          settingsPath: "/home/u/.config/project-index/settings.yaml",
          sources: [
            {
              id: "sample",
              config: ["/home/u/repo/sample/project-index.yaml"],
              enabled: true,
              scope: { read: ["/home/u/repo/sample/**"], write: null },
              status: "serving",
            },
          ],
        }),
      ),
    ],
  },
} satisfies Meta<typeof NotFoundScreen>;

export default meta;
type Story = StoryObj<typeof meta>;

export const SourceNotServed: Story = {
  args: {
    data: {
      missing: "not_served",
      value: "broken",
      errors: [{ path: "documents[0].paths", reason: "必須のキーが無い" }],
    },
  },
};
