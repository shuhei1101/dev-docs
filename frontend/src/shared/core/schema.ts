import { z } from "zod";

/** problem+json の本文（他のキーは passthrough） */
export const ProblemSchema = z
  .object({
    type: z.string(),
    title: z.string(),
    status: z.number(),
    detail: z.string(),
    nextSteps: z.array(z.string()).default([]),
    errors: z
      .array(z.object({ path: z.string(), reason: z.string() }))
      .optional(),
  })
  .passthrough();

/** 画面の API の 503 の problem+json の最上位。project-index に接続できなかったアドレスと理由 */
export const ProjectIndexUnreachableSchema = z.object({
  projectIndex: z.object({ address: z.string(), reason: z.string() }),
});

/** 文書の取得の 404 の problem+json の最上位 */
export const MissingSchema = z.object({
  missing: z.enum(["source", "not_served", "ref", "doc"]),
  value: z.string(),
  errors: z
    .array(z.object({ path: z.string(), reason: z.string() }))
    .optional(),
});
