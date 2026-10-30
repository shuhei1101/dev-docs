import type { z } from "zod";

import { ProblemSchema } from "@/shared/core/schema";

export type Problem = z.infer<typeof ProblemSchema>;

const PROBLEM_JSON = "application/problem+json";

/** API の失敗を表す例外の根 */
export class AppError extends Error {
  readonly status: number;
  readonly problem: Problem | null;

  constructor(message: string, status: number, problem: Problem | null = null) {
    super(message);
    this.name = new.target.name;
    this.status = status;
    this.problem = problem;
  }

  /** 失敗した応答からステータスに合う例外を作る */
  static async fromResponse(response: Response): Promise<AppError> {
    let problem: Problem | null = null;
    if (response.headers.get("Content-Type")?.includes(PROBLEM_JSON)) {
      const parsed = ProblemSchema.safeParse(await response.json().catch(() => null));
      problem = parsed.success ? parsed.data : null;
    }
    const message = problem?.detail ?? `HTTP ${response.status}`;
    switch (response.status) {
      case 400:
      case 422:
        return new ClientValueError(message, response.status, problem);
      case 401:
        return new ClientAuthError(message, response.status, problem);
      case 404:
        return new NotFoundError(message, response.status, problem);
      case 409:
        return new VersionConflictError(message, response.status, problem);
      case 429:
        return new RateLimitError(message, response.status, problem);
      default:
        return new AppError(message, response.status, problem);
    }
  }
}

/** 400・422。`problem.errors` を持つ */
export class ClientValueError extends AppError {}
/** 401 */
export class ClientAuthError extends AppError {}
/** 404。`problem.missing` で見つからなかったものを持つ */
export class NotFoundError extends AppError {}
/** 409 */
export class VersionConflictError extends AppError {}
/** 429 */
export class RateLimitError extends AppError {}
