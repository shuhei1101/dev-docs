import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { StatusBadge } from "@/features/settings/settings/components/status-badge";
import { settingsSource } from "@tests/helpers/fixtures";

test("test_status_badge", () => {
  const source = settingsSource("a", {
    status: "not_served",
    errors: [{ path: "documents[0]", reason: "paths が必要です" }],
  });

  render(<StatusBadge source={source as never} />);

  expect(screen.getByText("配信していない")).toBeInTheDocument();
  expect(screen.getByText(/起動時の検証で外しました。/)).toBeInTheDocument();
  expect(screen.getByText(/documents\[0\] paths が必要です/)).toBeInTheDocument();
});

test("test_status_badge_when_old_config_version", () => {
  const source = settingsSource("a", { configVersion: { config: "1", server: "2" } });

  render(<StatusBadge source={source as never} />);

  expect(screen.getByText("設定のバージョン 1（サーバーが読めるのは 2）")).toBeInTheDocument();
});
