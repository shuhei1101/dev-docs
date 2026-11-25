import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { SidebarToggle } from "@/features/docs/doc-view/components/sidebar-toggle";

test("test_sidebar_toggle", async () => {
  const onOpenChange = vi.fn();
  render(<SidebarToggle open onOpenChange={onOpenChange} />);

  const button = screen.getByRole("button", { name: "サイドバーを閉じる" });
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(button).toHaveAttribute("aria-controls", "doc-sidebar");
  await userEvent.click(button);

  expect(onOpenChange).toHaveBeenCalledWith(false);
});

test("test_sidebar_toggle_when_closed", async () => {
  const onOpenChange = vi.fn();
  render(<SidebarToggle open={false} onOpenChange={onOpenChange} />);

  const button = screen.getByRole("button", { name: "サイドバーを開く" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(button).not.toHaveAttribute("aria-controls");
  await userEvent.click(button);

  expect(onOpenChange).toHaveBeenCalledWith(true);
});
