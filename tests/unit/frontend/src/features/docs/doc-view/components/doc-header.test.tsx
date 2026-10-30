import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { DocHeader } from "@/features/docs/doc-view/components/doc-header";

test("test_doc_header", () => {
  const { container } = render(
    <DocHeader title="A" kind="設計書" path="docs/a" updatedAt="2026-10-26T14:40:00Z" />,
  );

  expect(screen.getByRole("heading", { level: 1, name: "A" })).toBeInTheDocument();
  expect(screen.getByText("更新 10/26 23:40 JST")).toBeInTheDocument();
  expect(container.querySelector("time")).toHaveAttribute("datetime", "2026-10-26T14:40:00Z");
});
