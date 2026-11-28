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
    onPendingPanelToggle: fn(),
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
  globals: { viewport: { value: "mobile1", isRotated: false } },
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
  globals: { viewport: { value: "mobile1", isRotated: false } },
};

export const NotFoundWithoutSource: Story = {
  args: { screen: "not-found", sources },
};

export const DarkScheme: Story = { args: { ...docView, colorScheme: "dark" } };

export const DocViewWithPendingEdits: Story = {
  args: { ...docView, commentCount: 2, pendingEditCount: 3 },
};

export const DocViewWithPendingEditsNarrow: Story = {
  args: { ...docView, commentCount: 2, pendingEditCount: 3 },
  globals: { viewport: { value: "mobile1", isRotated: false } },
};

const metadata = {
  screen: "metadata",
  sources,
  currentSource: "sample",
  pendingEditCount: 3,
} as const;

export const Metadata: Story = { args: metadata };

export const MetadataNarrow: Story = {
  args: metadata,
  globals: { viewport: { value: "mobile1", isRotated: false } },
};

const longItems = {
  screen: "doc-view" as const,
  sources: [
    { id: "mindstella-nandemo-kaiwa-74ba1a", writable: true },
    { id: "aituber-material-templates", writable: false },
    { id: "sample", writable: true },
  ],
  currentSource: "mindstella-nandemo-kaiwa-74ba1a",
  refs: {
    git: true,
    defaultRef: "develop",
    branches: [
      {
        name: "feat/screen/metadata-only-kinds-and-excluded-docs",
        commit: "5b3f8e2",
      },
    ],
    tags: [{ name: "v1.12.0", commit: "5b3f8e2" }],
    commits: [
      {
        commit: "5b3f8e2",
        date: "2026-11-25T01:16:00+09:00",
        subject: "docs: PR ドキュメント #331 の要件と計画書を記入",
      },
    ],
  },
  currentRef: "feat/screen/metadata-only-kinds-and-excluded-docs",
};

export const LongItems: Story = { args: longItems };

export const LongItemsNarrow: Story = {
  args: longItems,
  globals: { viewport: { value: "mobile1", isRotated: false } },
};
