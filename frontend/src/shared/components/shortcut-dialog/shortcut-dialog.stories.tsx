import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";

import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";

const meta = {
  title: "Layout/ShortcutDialog",
  component: ShortcutDialog,
  args: { open: true, onOpenChange: fn(), screen: "doc-view", singleKey: true },
} satisfies Meta<typeof ShortcutDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const DocView: Story = { args: { screen: "doc-view" } };

export const Settings: Story = { args: { screen: "settings" } };

export const NotFound: Story = { args: { screen: "not-found" } };

export const SingleKeyOff: Story = {
  args: { screen: "doc-view", singleKey: false },
};
