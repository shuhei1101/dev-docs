import { expect, test, vi } from "vitest";

import { createLogger } from "@/shared/lib/logger";

test("test_create_logger", () => {
  const sink = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  const logger = createLogger(sink);

  logger.error("api_failed", { status: 500, error: new Error("x") });

  expect(sink.error).toHaveBeenCalledTimes(1);
  const line = JSON.parse(sink.error.mock.calls[0][0] as string);
  expect(line.level).toBe("error");
  expect(line.event).toBe("api_failed");
  expect(line.status).toBe(500);
  expect(line.error.message).toBe("x");
});
