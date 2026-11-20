import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";

const ROWS = [
  ["種類", "module"],
  ["スクリプト", "scripts/convert_module.py"],
  ["原因", "Traceback (most recent call last): KeyError: 'components'"],
];

/** 見出し・説明・一覧・ボタンを並べた中身 */
const Content = () => (
  <>
    <AlertTitle>本文を変換できませんでした</AlertTitle>
    <AlertDescription className="space-y-3">
      <p>
        配信元の変換のスクリプトが失敗して終わりました。スクリプトを修正してから、再読み込みしてください。
      </p>
      <dl className="space-y-1">
        {ROWS.map(([label, value]) => (
          <div key={label} className="flex gap-4">
            <dt className="w-24 shrink-0 font-medium">{label}</dt>
            <dd className="font-mono text-xs break-all">{value}</dd>
          </div>
        ))}
      </dl>
      <Button variant="outline" size="sm">
        再読み込み
      </Button>
    </AlertDescription>
  </>
);

const meta = {
  title: "Shared/UI/Alert",
  component: Alert,
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-xl bg-background p-8">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Alert>;

export default meta;
type Story = StoryObj<typeof meta>;

/** 通常の通知 */
export const Default: Story = {
  args: { children: <Content /> },
};

/** エラー（見出し・説明・一覧・ボタン） */
export const Destructive: Story = {
  args: { variant: "destructive", children: <Content /> },
};

/** エラー（ダークのテーマ） */
export const DestructiveDark: Story = {
  args: { variant: "destructive", children: <Content /> },
  globals: { theme: "dark" },
};

/** エラー（見出しを持たず、文だけ） */
export const DestructiveMessageOnly: Story = {
  args: {
    variant: "destructive",
    children: "配信元を削除できませんでした。もう一度お試しください。",
  },
};
