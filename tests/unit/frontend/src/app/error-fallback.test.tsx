import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ErrorFallback } from "@/app/error-fallback";
import { logger } from "@/shared/lib/logger";

vi.mock("@/shared/lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

test("test_error_fallback", () => {
  render(<ErrorFallback error={new Error("x")} reset={() => {}} />);

  expect(screen.getByText("画面を表示できませんでした。")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /再読み込み/ })).toBeInTheDocument();
  expect(logger.error).toHaveBeenCalledTimes(1);
  expect(vi.mocked(logger.error).mock.calls[0][0]).toBe("render_failed");
});
