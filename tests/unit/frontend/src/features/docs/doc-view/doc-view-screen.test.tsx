import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test, vi } from "vitest";

import { usePreferencesStore } from "@/shared/stores/preferences";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { docEdit, documentResponse, group, page, refsResponse, settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderApp } from "@tests/helpers/render-app";

const mount = vi.hoisted(() => vi.fn());

vi.mock("https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@develop/dist/index.js", () => ({ mount }));

const useHandlers = (document: Record<string, unknown>) =>
  server.use(
    http.get("/_api/sources/:source/docs/*", () => HttpResponse.json(document)),
    http.get("/_api/sources/:source/docs", () => HttpResponse.json(document)),
    http.get("/_api/sources/:source/refs", () => HttpResponse.json(refsResponse())),
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(settingsView([settingsSource("s")])),
    ),
  );

beforeEach(() => {
  usePreferencesStore.setState({ sidebarOpen: true, sidebarWidth: 240 });
  mount.mockReset();
  mount.mockReturnValue({ update: vi.fn(), destroy: vi.fn() });
});

test("test_doc_view_screen", async () => {
  useHandlers(documentResponse());

  renderApp("/s/a.md");

  expect(await screen.findByRole("heading", { level: 1, name: "A" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "パンくず" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "A" })).toHaveAttribute("aria-current", "page");
  await waitFor(() => expect(document.title).toBe("A | s | dev-docs"));
  await waitFor(() => expect(mount).toHaveBeenCalled());
  expect((mount.mock.calls[0][1] as { markdown: string }).markdown).not.toContain("# A");
});

test("test_doc_view_screen_when_empty_tab", async () => {
  useHandlers(documentResponse());
  const { router } = renderApp("/s/a.md");
  await screen.findByRole("heading", { level: 1, name: "A" });

  await userEvent.click(screen.getByText("規約"));

  expect(await screen.findByText("規約の文書はありません")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_doc_view_screen_when_conversion_error", async () => {
  useHandlers(
    documentResponse({
      markdown: null,
      conversionError: { reason: "timeout", kind: "rules", script: "scripts/convert.py", detail: "x" },
      tabs: [{ title: "設計書", active: true, items: [group("設計", [page("A", "a.md")])] }],
    }),
  );

  renderApp("/s/a.md");

  expect(await screen.findByText("本文を変換できませんでした")).toBeInTheDocument();
  expect(mount).not.toHaveBeenCalled();
});

test("test_doc_view_screen_when_sidebar_closed", async () => {
  useHandlers(documentResponse());
  renderApp("/s/a.md");
  await screen.findByRole("heading", { level: 1, name: "A" });

  await userEvent.click(screen.getByRole("button", { name: "サイドバーを閉じる" }));

  expect(screen.queryByRole("navigation", { name: "文書の一覧" })).not.toBeInTheDocument();
  expect(screen.queryByRole("separator", { name: "サイドバーの幅" })).not.toBeInTheDocument();
  expect(usePreferencesStore.getState().sidebarOpen).toBe(false);

  await userEvent.click(screen.getByRole("button", { name: "サイドバーを開く" }));

  expect(screen.getByRole("navigation", { name: "文書の一覧" })).toBeInTheDocument();
  expect(document.getElementById("doc-sidebar")).toHaveStyle({ width: "240px" });
});

test("test_doc_view_screen_when_edit_fields", async () => {
  useHandlers(documentResponse({ path: "notes/n1", edit: docEdit() }));

  renderApp("/s/notes/n1?edit=fields");

  expect(await screen.findByRole("button", { name: "表示した場所で修正" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "概要 を編集" })).toBeInTheDocument();
});

test("test_doc_view_screen_when_not_editable", async () => {
  useHandlers(documentResponse({ edit: null }));

  renderApp("/s/a.md?edit=file");

  expect(await screen.findByRole("heading", { level: 1, name: "A" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "編集" })).not.toBeInTheDocument();
  await waitFor(() => expect(mount).toHaveBeenCalled());
});

test("test_doc_view_screen_when_pending_panel", async () => {
  useHandlers(documentResponse({ path: "notes/n1", edit: docEdit() }));
  usePendingEditsStore.setState({
    bySource: {
      s: [
        {
          key: "body:n1:@file",
          kind: "body",
          op: "update",
          docId: "n1",
          docKind: "note",
          expectedVersion: "v-n1",
          docPath: "notes/n1.yaml",
          values: { "@file": "title: n2\n" },
          before: { "@file": "title: n1\n" },
          label: "ファイル全体（notes/n1.yaml）",
        },
      ],
    },
    baseCommitBySource: { s: "ccc3333" },
  });
  const { router } = renderApp("/s/notes/n1");
  await screen.findByRole("heading", { level: 1 });

  await userEvent.click(screen.getByRole("button", { name: /レビュー中/ }));

  expect(router.state.location.pathname).toBe("/s/notes/n1");
  await userEvent.click(await screen.findByText("ファイル全体（notes/n1.yaml）"));
  await waitFor(() => expect(router.state.location.search).toMatchObject({ edit: "file" }));
  expect(router.state.location.pathname).toBe("/s/notes/n1.yaml");
});

test("test_doc_view_screen_when_layout", async () => {
  useHandlers(documentResponse());

  renderApp("/s/a.md");

  const heading = await screen.findByRole("heading", { level: 1, name: "A" });
  const scroll = document.getElementById("doc-scroll");
  expect(scroll).not.toBeNull();
  expect(scroll).toContainElement(heading);
  expect(scroll?.closest(".h-dvh")).toHaveClass("overflow-hidden");
  expect(document.getElementById("doc-sidebar")?.className ?? "").not.toMatch(/\bsticky\b/);
});

const fireBeforeUnload = () => {
  const event = new Event("beforeunload", { cancelable: true });
  act(() => {
    window.dispatchEvent(event);
  });
  return event;
};

const pendingEdit = {
  key: "body:n1:@file",
  kind: "body",
  op: "update",
  docId: "n1",
  docKind: "note",
  expectedVersion: "v-n1",
  docPath: "notes/n1.yaml",
  values: { "@file": "title: n2\n" },
  before: { "@file": "title: n1\n" },
  label: "ファイル全体（notes/n1.yaml）",
} as const;

test("test_doc_view_screen_when_comment_panel_in_url", async () => {
  useHandlers(documentResponse());
  const { router } = renderApp("/s/a.md");
  await screen.findByRole("heading", { level: 1, name: "A" });
  const length = window.history.length;

  await userEvent.click(screen.getByRole("button", { name: /^コメント \d+ 件$/ }));

  await waitFor(() => expect(router.state.location.search).toMatchObject({ panel: "comments" }));
  expect(await screen.findByRole("dialog", { name: /コメント/ })).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /レビュー中/ }));

  await waitFor(() => expect(router.state.location.search).toMatchObject({ panel: "edits" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: /コメント/ })).not.toBeInTheDocument());
  expect(window.history.length).toBe(length);
});

test("test_doc_view_screen_when_leave_guard", async () => {
  useHandlers(documentResponse());
  usePendingEditsStore.setState({ bySource: { s: [] }, baseCommitBySource: {} });
  renderApp("/s/a.md");
  await screen.findByRole("heading", { level: 1, name: "A" });

  expect(fireBeforeUnload().defaultPrevented).toBe(false);
  act(() => usePendingEditsStore.setState({ bySource: { s: [pendingEdit as never] }, baseCommitBySource: { s: "ccc3333" } }));

  expect(fireBeforeUnload().defaultPrevented).toBe(true);
});

test("test_doc_view_screen_when_scroll_restored", async () => {
  // jsdom は配置を計算せず `scrollTop` の書き込みを捨てるので、要素ごとに書き込んだ値を保つ
  const positions = new WeakMap<Element, number>();
  const descriptor = Object.getOwnPropertyDescriptor(Element.prototype, "scrollTop");
  Object.defineProperty(Element.prototype, "scrollTop", {
    get() {
      return positions.get(this as Element) ?? 0;
    },
    set(value: number) {
      positions.set(this as Element, value);
    },
    configurable: true,
  });
  // jsdom の要素は `scrollTo` を持たないので、`top` を書き込む偽物を配置する
  Object.defineProperty(Element.prototype, "scrollTo", {
    value(this: Element, options?: ScrollToOptions | number, top?: number) {
      const next = typeof options === "object" ? options.top : top;
      if (next !== undefined) positions.set(this, next);
    },
    configurable: true,
  });
  try {
    useHandlers(documentResponse());
    const { router } = renderApp("/s/a.md");
    await screen.findByRole("heading", { level: 1, name: "A" });
    const body = () => document.querySelector('[data-scroll-restoration-id="doc-body"]');
    expect(body()).not.toBeNull();

    const first = body() as Element;
    first.scrollTop = 400;
    first.dispatchEvent(new Event("scroll", { bubbles: true }));
    await act(() => router.navigate({ to: "/$source/$", params: { source: "s", _splat: "b.md" } }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/s/b.md"));
    expect((body() as Element).scrollTop).toBe(0);

    act(() => router.history.back());

    await waitFor(() => expect(router.state.location.pathname).toBe("/s/a.md"));
    await waitFor(() => expect((body() as Element).scrollTop).toBe(400));
  } finally {
    Reflect.deleteProperty(Element.prototype, "scrollTo");
    if (descriptor) Object.defineProperty(Element.prototype, "scrollTop", descriptor);
  }
});
