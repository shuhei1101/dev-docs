import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ErrorFallback } from "@/app/error-fallback";
import { AppError } from "@/shared/core/app-error";
import { logger } from "@/shared/lib/logger";

vi.mock("@/shared/lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

test("test_error_fallback", () => {
  render(<ErrorFallback error={new Error("x")} reset={() => {}} />);

  expect(screen.getByText("画面を表示できませんでした。")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /再読み込み/ }),
  ).toBeInTheDocument();
  expect(logger.error).toHaveBeenCalledTimes(1);
  expect(vi.mocked(logger.error).mock.calls[0][0]).toBe("render_failed");
});

test("test_error_fallback_when_project_index_failed", () => {
  vi.mocked(logger.error).mockClear();
  const error = new AppError(
    "project-index が要求を処理できませんでした",
    502,
    {
      type: "about:blank",
      title: "ProjectIndexResponseError",
      status: 502,
      detail:
        "project-index（http://127.0.0.1:8786）が要求を処理できませんでした。git archive …",
      nextSteps: [],
      projectIndex: {
        address: "http://127.0.0.1:8786",
        reason: "git archive …: 20 秒を超えたため止めました",
        kind: "failed",
      },
    },
  );

  render(<ErrorFallback error={error} reset={() => {}} />);

  expect(
    screen.getByText("project-index が要求を処理できませんでした"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("git archive …: 20 秒を超えたため止めました"),
  ).toBeInTheDocument();
  expect(logger.error).toHaveBeenCalledTimes(1);
  expect(vi.mocked(logger.error).mock.calls[0][0]).toBe(
    "project_index_unreachable",
  );
});
