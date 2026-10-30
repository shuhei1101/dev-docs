import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { DocToc } from "@/features/docs/doc-view/components/doc-toc";

beforeEach(() => {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

test("test_doc_toc", () => {
  const items = [
    { id: "a", text: "A", level: 2 as const },
    { id: "b", text: "B", level: 2 as const },
  ];

  render(<DocToc items={items} changed={new Set(["A"])} />);

  const rowA = screen.getByRole("link", { name: /A/ });
  const rowB = screen.getByRole("link", { name: /B/ });
  expect(rowA.textContent).toContain("変更");
  expect(rowB.textContent).not.toContain("変更");
});
