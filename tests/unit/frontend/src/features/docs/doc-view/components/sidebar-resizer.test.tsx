import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, expect, test, vi } from "vitest";

import { SidebarResizer } from "@/features/docs/doc-view/components/sidebar-resizer";

beforeAll(() => {
  // jsdom の要素はポインターのキャプチャを持たない
  HTMLElement.prototype.setPointerCapture ??= () => {};
});

const drag = (width: number, from: number, to: number) => {
  const onWidthChange = vi.fn();
  render(<SidebarResizer width={width} onWidthChange={onWidthChange} />);
  const separator = screen.getByRole("separator", { name: "サイドバーの幅" });
  fireEvent.pointerDown(separator, { button: 0, pointerId: 1, clientX: from });
  fireEvent.pointerMove(separator, { pointerId: 1, clientX: to });
  fireEvent.pointerUp(separator, { pointerId: 1, clientX: to });
  return onWidthChange;
};

test("test_sidebar_resizer_when_dragged", () => {
  expect(drag(240, 100, 150)).toHaveBeenLastCalledWith(290);
});

test("test_sidebar_resizer_when_dragged_over_max", () => {
  expect(drag(400, 100, 300)).toHaveBeenLastCalledWith(480);
});

test("test_sidebar_resizer_when_key", async () => {
  const onWidthChange = vi.fn();
  render(<SidebarResizer width={240} onWidthChange={onWidthChange} />);
  screen.getByRole("separator", { name: "サイドバーの幅" }).focus();

  await userEvent.keyboard("{ArrowRight}{Home}{End}");

  expect(onWidthChange.mock.calls.map(([width]) => width)).toEqual([256, 192, 480]);
});

test("test_sidebar_resizer_when_double_clicked", async () => {
  const onWidthChange = vi.fn();
  render(<SidebarResizer width={400} onWidthChange={onWidthChange} />);

  await userEvent.dblClick(screen.getByRole("separator", { name: "サイドバーの幅" }));

  expect(onWidthChange).toHaveBeenLastCalledWith(240);
});
