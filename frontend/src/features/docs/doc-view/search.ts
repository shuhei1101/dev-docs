import { z } from "zod";

/** 文書の画面の編集の表示（`fields` は表示した場所で修正、`file` はファイル全体の編集） */
export const DocEditModeSchema = z.enum(["fields", "file"]);

export type DocEditMode = z.infer<typeof DocEditModeSchema>;

/** 文書の画面の URL のクエリ。解析できない値は捨てる */
export const DocViewSearchSchema = z.object({
  rev: z.string().min(1).optional().catch(undefined),
  base: z.string().min(1).optional().catch(undefined),
  tab: z.coerce.number().int().min(0).optional().catch(undefined),
  edit: DocEditModeSchema.optional().catch(undefined),
  // `edits` ならレビュー中のパネルを開いて始める（メタデータの画面のレビュー中のパネルから移るとき）
  panel: z.enum(["comments", "edits"]).optional().catch(undefined),
});

export type DocViewSearch = z.infer<typeof DocViewSearchSchema>;
