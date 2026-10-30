import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { DiffBanner } from "@/features/docs/doc-view/components/diff-banner";
import { refsResponse } from "@tests/helpers/fixtures";

test("test_diff_banner", async () => {
  render(
    <DiffBanner
      base="deadbee"
      head="main"
      refs={refsResponse() as never}
      onChange={vi.fn()}
      onClear={vi.fn()}
    />,
  );

  await userEvent.click(screen.getByRole("combobox", { name: "比較元" }));

  const options = await screen.findAllByRole("option");
  expect(options[0]).toHaveTextContent("deadbee");
});

test("test_diff_banner_when_clear", async () => {
  const onClear = vi.fn();
  render(
    <DiffBanner
      base="v0.1.0"
      head="main"
      refs={refsResponse() as never}
      onChange={vi.fn()}
      onClear={onClear}
    />,
  );

  await userEvent.click(
    screen.getByRole("button", { name: "差分の強調を解除" }),
  );

  expect(onClear).toHaveBeenCalledTimes(1);
});
