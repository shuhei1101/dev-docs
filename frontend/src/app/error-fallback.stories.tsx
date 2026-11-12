import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";

import { ErrorFallback } from "@/app/error-fallback";
import { AppError } from "@/shared/core/app-error";

const meta = {
  title: "App/ErrorFallback",
  component: ErrorFallback,
  args: { reset: fn() },
} satisfies Meta<typeof ErrorFallback>;

export default meta;
type Story = StoryObj<typeof meta>;

export const RenderFailed: Story = {
  args: { error: new Error("描画中の例外") },
};

export const ProjectIndexUnreachable: Story = {
  args: {
    error: new AppError("project-index に接続できませんでした", 503, {
      type: "about:blank",
      title: "Service Unavailable",
      status: 503,
      detail: "project-index に接続できませんでした",
      nextSteps: [],
      projectIndex: {
        address: "http://127.0.0.1:8786",
        reason: "接続を拒否されました（Connection refused）",
      },
    }),
  },
};
