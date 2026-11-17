import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";

import { ProjectIndexUnreachableAlert } from "@/shared/components/project-index-unreachable";

const meta = {
  title: "Shared/ProjectIndexUnreachableAlert",
  component: ProjectIndexUnreachableAlert,
  args: { address: "http://127.0.0.1:8786", onReload: fn() },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-xl p-8">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProjectIndexUnreachableAlert>;

export default meta;
type Story = StoryObj<typeof meta>;

/** project-index が接続を断った */
export const Unreachable: Story = {
  args: {
    kind: "unreachable",
    reason: "接続を拒否されました（Connection refused）",
  },
};

/** 文書の取得の制限時間の中で、project-index から応答が無かった */
export const TimedOut: Story = {
  args: {
    kind: "timeout",
    reason: "45 秒以内に応答がありませんでした",
  },
};

/** project-index が要求の処理に失敗した（project-index の 500） */
export const Failed: Story = {
  args: {
    kind: "failed",
    reason:
      "要求の処理に失敗した（GET・/sources/project-index/config・git archive --format=tar 006a49034a210dfb1eb2f8b998abad760c002f5b: 20 秒を超えたため止めました）",
  },
};
