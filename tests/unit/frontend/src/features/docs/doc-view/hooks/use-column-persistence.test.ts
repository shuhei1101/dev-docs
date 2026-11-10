import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { useColumnPersistence } from "@/features/docs/doc-view/hooks/use-column-persistence";

const viewPutColumns = vi.hoisted(() => vi.fn());
const toastError = vi.hoisted(() => vi.fn());

vi.mock("@/shared/api/generated/view/view", () => ({ viewPutColumns }));
vi.mock("sonner", () => ({ toast: { error: toastError } }));

const wrapper = ({ children }: { children: ReactNode }) =>
  createElement(QueryClientProvider, { client: new QueryClient() }, children);

beforeEach(() => {
  viewPutColumns.mockReset();
  toastError.mockReset();
});

test("test_use_column_persistence", async () => {
  viewPutColumns.mockResolvedValue({});
  const { result } = renderHook(
    () => useColumnPersistence({ source: "s", columnKeys: ["t2"] }),
    { wrapper },
  );

  result.current({ tableIndex: 0, hidden: ["備考"] });

  await vi.waitFor(() => expect(viewPutColumns).toHaveBeenCalledTimes(1));
  expect(viewPutColumns).toHaveBeenCalledWith("s", { table: "t2", hidden: ["備考"] });
});

test("test_use_column_persistence_when_failed", async () => {
  viewPutColumns.mockRejectedValue(new Error("failed"));
  const { result } = renderHook(
    () => useColumnPersistence({ source: "s", columnKeys: ["t2"] }),
    { wrapper },
  );

  result.current({ tableIndex: 0, hidden: ["備考"] });

  await vi.waitFor(() => expect(toastError).toHaveBeenCalledWith("列の表示を保存できませんでした。"));
});
