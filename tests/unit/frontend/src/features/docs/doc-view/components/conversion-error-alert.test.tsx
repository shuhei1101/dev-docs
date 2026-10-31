import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ConversionErrorAlert } from "@/features/docs/doc-view/components/conversion-error-alert";

test("test_conversion_error_alert", () => {
  render(
    <ConversionErrorAlert
      error={
        { reason: "timeout", kind: "rules", script: "scripts/convert.py", detail: "10 秒を超えました" } as never
      }
      onRetry={vi.fn()}
    />,
  );

  expect(screen.getByRole("alert")).toBeInTheDocument();
  expect(screen.getByText("本文を変換できませんでした")).toBeInTheDocument();
  expect(
    screen.getByText(
      "配信元の変換のスクリプトが制限時間を超えたため、止めました。スクリプトを修正してから、再読み込みしてください。",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("種類")).toBeInTheDocument();
  expect(screen.getByText("スクリプト")).toBeInTheDocument();
  expect(screen.getByText("原因")).toBeInTheDocument();
});

test("test_conversion_error_alert_when_yaml", () => {
  render(
    <ConversionErrorAlert
      error={
        { reason: "invalid_yaml", kind: "rules", file: "docs/a.yaml", line: 12, column: 3, detail: "x" } as never
      }
      onRetry={vi.fn()}
    />,
  );

  expect(screen.getByText("場所")).toBeInTheDocument();
  expect(screen.getByText("12 行 3 列")).toBeInTheDocument();
});
