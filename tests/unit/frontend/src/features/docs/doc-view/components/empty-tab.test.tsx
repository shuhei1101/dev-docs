import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { EmptyTab } from "@/features/docs/doc-view/components/empty-tab";

test("test_empty_tab_when_not_git", () => {
  render(<EmptyTab tab={{ title: "規約", active: true, items: [] } as never} index={1} ref={null} />);

  expect(screen.getByText("規約の文書はありません")).toBeInTheDocument();
  expect(screen.getByText(/nav\.tabs\[1\]\.paths/)).not.toHaveTextContent("、リビジョン");
});
