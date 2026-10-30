import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";

import { Topbar } from "@/shared/components/topbar/topbar";

const refs = {
  git: true,
  defaultRef: "develop",
  branches: [
    { name: "develop", commit: "8b1d4e0" },
    { name: "feat/frontend/react-spa", commit: "7c0aa11" },
  ],
  tags: [{ name: "v0.1.0", commit: "3f2a9c1" }],
  commits: [
    {
      commit: "8b1d4e0",
      date: "2026-10-26T11:30:00+09:00",
      subject: "docs: 文書を追加",
    },
    {
      commit: "7c0aa11",
      date: "2026-10-25T11:30:00+09:00",
      subject: "docs: 規約を修正",
    },
  ],
};

const sources = [
  { id: "sample", writable: true },
  { id: "knowledge", writable: false },
  { id: "notes", writable: true },
];

const meta = {
  title: "Layout/Topbar",
  component: Topbar,
  args: {
    screen: "doc-view",
    colorScheme: "system",
    onSourceSelect: fn(),
    onRefSelect: fn(),
    onCompareStart: fn(),
    onSearchOpen: fn(),
    onCommentPanelToggle: fn(),
    onSidebarOpen: fn(),
    onColorSchemeToggle: fn(),
  },
} satisfies Meta<typeof Topbar>;

export default meta;
type Story = StoryObj<typeof meta>;

const docView = {
  screen: "doc-view",
  sources,
  currentSource: "sample",
  refs,
  currentRef: "develop",
} as const;

export const DocView: Story = { args: { ...docView, commentCount: 2 } };

export const DocViewNarrow: Story = {
  args: { ...docView, commentCount: 2 },
  parameters: { viewport: { defaultViewport: "mobile1" } },
};

export const DocViewNoComments: Story = {
  args: { ...docView, commentCount: 0 },
};

export const NonGitSource: Story = {
  args: {
    ...docView,
    currentSource: "notes",
    refs: { ...refs, git: false, branches: [], tags: [], commits: [] },
  },
};

export const Settings: Story = { args: { screen: "settings" } };

export const NotFound: Story = {
  args: { screen: "not-found", sources, currentSource: "sample", refs },
};

export const NotFoundNarrow: Story = {
  args: { screen: "not-found", sources, currentSource: "sample", refs },
  parameters: { viewport: { defaultViewport: "mobile1" } },
};

export const NotFoundWithoutSource: Story = {
  args: { screen: "not-found", sources },
};

export const DarkScheme: Story = { args: { ...docView, colorScheme: "dark" } };
