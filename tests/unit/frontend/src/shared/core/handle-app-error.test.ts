import { toast } from "sonner";
import { beforeEach, expect, test, vi } from "vitest";

import { AppError } from "@/shared/core/app-error";
import { handleAppError } from "@/shared/core/handle-app-error";
import { logger } from "@/shared/lib/logger";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("@/shared/lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const serverError = () =>
  AppError.fromResponse(
    new Response(
      JSON.stringify({
        type: "urn:dev-docs:error:InternalError",
        title: "InternalError",
        status: 500,
        detail: "x",
        nextSteps: [],
      }),
      { status: 500, headers: { "Content-Type": "application/problem+json" } },
    ),
  );

beforeEach(() => {
  vi.clearAllMocks();
});

test("test_handle_app_error", async () => {
  handleAppError(await serverError());

  expect(toast.error).toHaveBeenCalledTimes(1);
  expect(toast.error).toHaveBeenCalledWith("x");
  expect(logger.error).toHaveBeenCalledTimes(1);
  expect(vi.mocked(logger.error).mock.calls[0][0]).toBe("app_error");
});

test("test_handle_app_error_when_message", async () => {
  handleAppError(await serverError(), {
    message: "列の表示を保存できませんでした。",
  });

  expect(toast.error).toHaveBeenCalledWith("列の表示を保存できませんでした。");
});

test("test_handle_app_error_when_unknown", () => {
  handleAppError(new TypeError("y"));

  expect(toast.error).toHaveBeenCalledWith("予期しないエラーが起きました。");
});
