import { expect, test } from "vitest";

import { AppError, ClientValueError, NotFoundError } from "@/shared/core/app-error";

const problemResponse = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });

test("test_from_response", async () => {
  const errors = [
    { path: "sources[1].config[0]", reason: "ファイルがありません" },
    { path: "sources[0].id", reason: "使えない文字があります" },
  ];
  const response = problemResponse(422, {
    type: "urn:dev-docs:error:ValidationFailedError",
    title: "ValidationFailedError",
    status: 422,
    detail: "端末の設定を保存できません",
    nextSteps: [],
    errors,
  });

  const error = await AppError.fromResponse(response);

  expect(error).toBeInstanceOf(ClientValueError);
  expect(error.status).toBe(422);
  expect(error.problem?.errors).toEqual(errors);
});

test("test_from_response_when_not_found", async () => {
  const missing = { kind: "doc", source: "s", ref: "main", path: "a.md" };
  const response = problemResponse(404, {
    type: "urn:dev-docs:error:DocumentNotFoundError",
    title: "DocumentNotFoundError",
    status: 404,
    detail: "文書がありません",
    nextSteps: [],
    missing,
  });

  const error = await AppError.fromResponse(response);

  expect(error).toBeInstanceOf(NotFoundError);
  expect(error.problem).toMatchObject({ missing });
});

test("test_from_response_when_not_problem", async () => {
  const response = new Response("<html>Bad Gateway</html>", {
    status: 502,
    headers: { "Content-Type": "text/html" },
  });

  const error = await AppError.fromResponse(response);

  expect(error.constructor).toBe(AppError);
  expect(error.problem).toBeNull();
  expect(error.message).toBe("HTTP 502");
});
