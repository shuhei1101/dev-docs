import { toast } from "sonner";

import { AppError } from "@/shared/core/app-error";
import { logger } from "@/shared/lib/logger";

/** 例外の種類に合う通知を出し、ログを書く */
export const handleAppError = (
  error: unknown,
  options: { message?: string } = {},
): void => {
  const message =
    options.message ??
    (error instanceof AppError
      ? (error.problem?.detail ?? "通信に失敗しました。")
      : "予期しないエラーが起きました。");
  toast.error(message);
  logger.error("app_error", {
    status: error instanceof AppError ? error.status : undefined,
    type: error instanceof AppError ? error.problem?.type : undefined,
    error,
  });
};
