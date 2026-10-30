import { z } from "zod";

/** 文書の画面の URL のクエリ。読めない値は捨てる */
export const DocViewSearchSchema = z.object({
  rev: z.string().min(1).optional().catch(undefined),
  base: z.string().min(1).optional().catch(undefined),
});

export type DocViewSearch = z.infer<typeof DocViewSearchSchema>;
