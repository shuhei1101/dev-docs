import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";

test("test_shortcut_dialog", () => {
  render(<ShortcutDialog open onOpenChange={vi.fn()} screen="doc-view" singleKey={false} />);

  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveTextContent("Ctrl");
  expect(dialog.textContent).not.toContain("/");
  expect(dialog.textContent).not.toContain("?");
});
