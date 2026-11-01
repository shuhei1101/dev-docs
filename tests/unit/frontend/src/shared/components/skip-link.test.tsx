import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { SkipLink } from "@/shared/components/skip-link";

test("test_skip_link", async () => {
  render(
    <>
      <SkipLink />
      <main id="main" tabIndex={-1}>
        本文
      </main>
    </>,
  );

  await userEvent.click(screen.getByRole("link", { name: "本文へスキップ" }));

  expect(screen.getByRole("main")).toHaveFocus();
});
