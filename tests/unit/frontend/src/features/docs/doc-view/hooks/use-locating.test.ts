import { act, renderHook } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { useLocating } from "@/features/docs/doc-view/hooks/use-locating";
import type { DocComment } from "@/features/docs/shared/comments/comment-store";

const comment = (docId: string) => ({ id: "c1", docId }) as DocComment;

test("test_use_locating", () => {
  const openDoc = vi.fn();
  const { result } = renderHook(() => useLocating("a", openDoc));

  act(() => result.current.locate(comment("b")));

  expect(openDoc).toHaveBeenCalledTimes(1);
  expect(openDoc).toHaveBeenCalledWith(comment("b"));
  expect(result.current.locating).toEqual(comment("b"));
});

test("test_use_locating_when_same_doc", () => {
  const openDoc = vi.fn();
  const { result } = renderHook(() => useLocating("a", openDoc));

  act(() => result.current.locate(comment("a")));

  expect(openDoc).not.toHaveBeenCalled();
  expect(result.current.locating).toEqual(comment("a"));
});

test("test_use_locating_when_doc_left", () => {
  const { result, rerender } = renderHook(
    ({ docId }) => useLocating(docId, vi.fn()),
    { initialProps: { docId: "a" } },
  );
  act(() => result.current.locate(comment("b")));

  rerender({ docId: "b" });
  expect(result.current.locating).toEqual(comment("b"));

  rerender({ docId: "c" });
  expect(result.current.locating).toBeNull();
});

test("test_use_locating_when_located", () => {
  const { result } = renderHook(() => useLocating("a", vi.fn()));
  act(() => result.current.locate(comment("a")));

  act(() => result.current.onLocated());

  expect(result.current.locating).toBeNull();
});
