import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import {
  ProjectIndexUnreachableAlert,
  toProjectIndexUnreachable,
} from "@/shared/components/project-index-unreachable";
import { AppError } from "@/shared/core/app-error";

const ADDRESS = "http://127.0.0.1:8786";

const problemOf = (status: number, projectIndex: Record<string, string>) =>
  new AppError("x", status, {
    type: "about:blank",
    title: "x",
    status,
    detail: "x",
    nextSteps: [],
    projectIndex,
  });

test("test_to_project_index_unreachable", () => {
  const error = problemOf(502, {
    address: ADDRESS,
    reason: "r",
    kind: "failed",
  });

  expect(toProjectIndexUnreachable(error)).toEqual({
    address: ADDRESS,
    reason: "r",
    kind: "failed",
  });
});

test("test_to_project_index_unreachable_when_kind_missing", () => {
  const error = problemOf(503, { address: ADDRESS, reason: "r" });

  expect(toProjectIndexUnreachable(error)?.kind).toBe("unreachable");
});

test("test_to_project_index_unreachable_when_other", () => {
  const notFound = new AppError("x", 404, null);

  expect(toProjectIndexUnreachable(notFound)).toBeNull();
  expect(toProjectIndexUnreachable(new Error("x"))).toBeNull();
});

test.each([
  ["unreachable", "project-index に接続できませんでした"],
  ["timeout", "project-index から応答がありませんでした"],
  ["failed", "project-index が要求を処理できませんでした"],
] as const)("test_project_index_unreachable_alert %s", (kind, title) => {
  render(
    <ProjectIndexUnreachableAlert
      kind={kind}
      address={ADDRESS}
      reason="理由の本文"
      onReload={() => {}}
    />,
  );

  expect(screen.getByText(title)).toBeInTheDocument();
  expect(screen.getByText(ADDRESS)).toBeInTheDocument();
  expect(screen.getByText("理由の本文")).toBeInTheDocument();
});

test("test_project_index_unreachable_alert_when_reload", async () => {
  const onReload = vi.fn();
  render(
    <ProjectIndexUnreachableAlert
      address={ADDRESS}
      reason="理由の本文"
      onReload={onReload}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "再読み込み" }));

  expect(onReload).toHaveBeenCalledTimes(1);
});
