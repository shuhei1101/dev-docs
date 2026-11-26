import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import type { DocumentEdit, DocumentResponse, PreviewResponse } from "@/shared/api/generated/model";
import { viewPostPreview } from "@/shared/api/generated/view/view";
import { type EditValue, type PendingEdit, usePendingEdits, usePendingEditsStore } from "@/shared/stores/pending-edits-store";

/** ファイル全体の編集の変更の `values` のキー */
export const WHOLE_FILE = "@file";

/** ファイル全体のエディタの入力が止まってから本文のプレビューを呼ぶまでのミリ秒 */
export const PREVIEW_DELAY_MS = 500;

/** 文書の取得の応答の本文の編集の情報（編集できない文書は `null`） */
export const docEditOf = (doc: DocumentResponse): DocumentEdit | null => doc.edit ?? null;

/** 本文の変更の `key`（リビジョンによらず、文書の ID と項目のパスで 1 つ） */
export const bodyEditKey = (edit: DocumentEdit, path: string): string => `body:${edit.docId}:${path}`;

type BodyTarget = { path: string; label: string; before: EditValue; value: EditValue };

/** 本文の項目かファイル全体の値を、編集中の変更のストアへ入れる（元の値に戻すと除かれる） */
export const upsertBodyEdit = (source: string, edit: DocumentEdit, { path, label, before, value }: BodyTarget) => {
  const pending: PendingEdit = {
    key: bodyEditKey(edit, path),
    kind: "body",
    op: "update",
    docId: edit.docId,
    docKind: edit.kind,
    expectedVersion: edit.version,
    docPath: edit.filePath,
    values: { [path]: value },
    before: { [path]: before },
    label: `${label}（${edit.filePath}）`,
  };
  usePendingEditsStore.getState().upsert(source, pending, edit.baseCommit);
};

/** 項目のパスの編集中の変更があれば、その値 */
export const usePendingBodyValue = (source: string, edit: DocumentEdit, path: string): EditValue | undefined => {
  const key = bodyEditKey(edit, path);
  return usePendingEdits(source).find((item) => item.key === key)?.values[path];
};

/** 文書の編集中の変更が、項目のパスとファイル全体のどちらにあるか */
export const usePendingBodyMode = (source: string, edit: DocumentEdit): { fields: boolean; file: boolean } => {
  const edits = usePendingEdits(source).filter((item) => item.kind === "body" && item.docId === edit.docId);
  return {
    fields: edits.some((item) => !(WHOLE_FILE in item.values)),
    file: edits.some((item) => WHOLE_FILE in item.values),
  };
};

/** 書き換えた YAML を種類のスキーマで変換した本文のプレビューの問い合わせ */
export const previewQueryOptions = (source: string, path: string, content: string) =>
  queryOptions<PreviewResponse>({
    queryKey: ["view", "preview", source, path, content],
    queryFn: ({ signal }) => viewPostPreview(source, { path, content }, { signal }),
    placeholderData: keepPreviousData,
    meta: { handleError: false },
  });
