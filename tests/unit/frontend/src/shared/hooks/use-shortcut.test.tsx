import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { useShortcut } from "@/shared/hooks/use-shortcut";
import { usePreferencesStore } from "@/shared/stores/preferences";

function Probe({ handler }: { handler: () => void }) {
  useShortcut("search", handler);
  return <input aria-label="入力欄" />;
}

beforeEach(() => {
  usePreferencesStore.setState({ singleKeyShortcuts: true });
});

test("test_use_shortcut", async () => {
  const handler = vi.fn();
  render(<Probe handler={handler} />);

  await userEvent.keyboard("/");

  expect(handler).toHaveBeenCalledTimes(1);
});

test("test_use_shortcut_when_input_focused", async () => {
  const handler = vi.fn();
  const view = render(<Probe handler={handler} />);
  await userEvent.click(view.getByLabelText("入力欄"));

  await userEvent.keyboard("/");
  expect(handler).not.toHaveBeenCalled();

  await userEvent.keyboard("{Control>}k{/Control}");
  expect(handler).toHaveBeenCalledTimes(1);
});

test("test_use_shortcut_when_single_key_off", async () => {
  usePreferencesStore.setState({ singleKeyShortcuts: false });
  const handler = vi.fn();
  render(<Probe handler={handler} />);

  await userEvent.keyboard("/");

  expect(handler).not.toHaveBeenCalled();
});
