import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

const MDMARK_URL =
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/mount.js";

const fake = () => {
  const handle = { update: vi.fn(), destroy: vi.fn() };
  const mount = vi.fn(() => handle);
  return { handle, mount };
};

const loadHook = async () => {
  vi.resetModules();
  return (await import("@/features/docs/doc-view/hooks/use-mdmark")).useMdmark;
};

const options = (markdown: string, docId = "s@main:a.md") =>
  ({ markdown, docId, commentStore: {} }) as never;

beforeEach(() => {
  vi.resetModules();
  vi.doUnmock(MDMARK_URL);
});

test("test_use_mdmark", async () => {
  const { handle, mount } = fake();
  vi.doMock(MDMARK_URL, () => ({ mount }));
  const useMdmark = await loadHook();
  const ref = { current: document.createElement("div") };

  const view = renderHook(({ markdown }) => useMdmark(ref, options(markdown)), {
    initialProps: { markdown: "# A" },
  });
  await waitFor(() => expect(mount).toHaveBeenCalledTimes(1));
  view.rerender({ markdown: "# B" });
  await waitFor(() => expect(handle.update).toHaveBeenCalledTimes(1));
  view.unmount();

  expect(handle.destroy).toHaveBeenCalledTimes(1);
  expect(mount).toHaveBeenCalledTimes(1);
});

test("test_use_mdmark_when_doc_changes", async () => {
  const { handle, mount } = fake();
  vi.doMock(MDMARK_URL, () => ({ mount }));
  const useMdmark = await loadHook();
  const ref = { current: document.createElement("div") };

  const view = renderHook(
    ({ docId }) => useMdmark(ref, options("# A", docId)),
    {
      initialProps: { docId: "s@main:a.md" },
    },
  );
  await waitFor(() => expect(mount).toHaveBeenCalledTimes(1));
  view.rerender({ docId: "s@main:b.md" });

  await waitFor(() => expect(mount).toHaveBeenCalledTimes(2));
  expect(handle.destroy.mock.invocationCallOrder[0]).toBeLessThan(
    mount.mock.invocationCallOrder[1],
  );
});

test("test_use_mdmark_when_load_failed", async () => {
  vi.doMock(MDMARK_URL, () => {
    throw new Error("load failed");
  });
  const errorLog = vi.fn();
  vi.doMock("@/shared/lib/logger", () => ({
    logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: errorLog },
  }));
  const useMdmark = await loadHook();
  const ref = { current: document.createElement("div") };

  const { result } = renderHook(() => useMdmark(ref, options("# A")));

  await waitFor(() => expect(result.current.error).toBeTruthy());
  expect(errorLog.mock.calls[0][0]).toBe("mdmark_load_failed");
});
