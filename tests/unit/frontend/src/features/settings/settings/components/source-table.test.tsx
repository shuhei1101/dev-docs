import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { SourceTable } from "@/features/settings/settings/components/source-table";
import { settingsSource } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

const sources = [settingsSource("a"), settingsSource("b", { status: "disabled", enabled: false })];

test("test_source_table", async () => {
  renderInRouter(<SourceTable sources={sources as never} onEdit={vi.fn()} onRemove={vi.fn()} />, "/_settings");

  expect(await screen.findByRole("link", { name: "a" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "b" })).toBeNull();
});

test("test_source_table_when_edit", async () => {
  const onEdit = vi.fn();
  renderInRouter(<SourceTable sources={sources as never} onEdit={onEdit} onRemove={vi.fn()} />, "/_settings");

  await userEvent.click(await screen.findByRole("button", { name: "b を編集" }));

  expect(onEdit).toHaveBeenCalledTimes(1);
  expect(onEdit).toHaveBeenCalledWith(1);
});
