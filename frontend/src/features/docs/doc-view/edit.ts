import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { docIdOf } from "@/features/docs/shared/comments/comment-store";
import { type PendingEdit, usePendingEdits, usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
import { apiClient } from "@/shared/adapters/api-client";
import type { DocumentResponse } from "@/shared/api/generated/model";

/** 本文の項目の値の型から選ぶ編集の部品 */
export type EditBlockType = "string" | "enum" | "markdown" | "table";

/** 表示した場所で修正できる本文の項目 1 つ（項目のパスと、スキーマの型から選んだ部品） */
export type EditBlock = {
  path: string;
  label: string;
  type: EditBlockType;
  /** 本文に描いたこの項目のブロック（変換が項目のパスの目印を付けた範囲の Markdown） */
  markdown: string;
  /** `table` は行ごとの列の値、それ以外は文字列 */
  value: string | Array<Record<string, string>>;
  options?: string[];
  columns?: string[];
};

/** 文書の本文の編集に要る情報 */
export type DocEdit = {
  editable: boolean;
  language: "yaml" | "markdown";
  /** 元のファイルの内容 */
  source: string;
  version: string;
  kind: string;
  /** 表示した場所で修正できる項目（Markdown の文書は持たない） */
  blocks: EditBlock[];
};

/** ファイル全体の編集の変更の項目のパス */
export const WHOLE_FILE = "@file";

/** 文書の取得の応答の本文の編集の情報 */
export const docEditOf = (doc: DocumentResponse): DocEdit | null =>
  (doc as DocumentResponse & { edit?: DocEdit }).edit ?? null;

const keyOf = (doc: DocumentResponse, path: string) => `body:${docIdOf(doc)}:${path}`;

type BodyEditArgs = { doc: DocumentResponse; edit: DocEdit; path: string; label: string; before: string; value: string };

/** 文書の本文の変更を、メタデータの変更と同じ編集中の変更に溜める */
export const upsertBodyEdit = ({ doc, edit, path, label, before, value }: BodyEditArgs) => {
  const pending: PendingEdit = {
    key: keyOf(doc, path),
    kind: "body",
    op: "update",
    docId: docIdOf(doc),
    docKind: edit.kind,
    expectedVersion: edit.version,
    docPath: doc.path,
    values: { [path]: value },
    before: { [path]: before },
    label: `${label}（${doc.path}）`,
  };
  usePendingEditsStore.getState().upsert(doc.source, pending, doc.ref ?? "");
};

/** 本文の項目の、編集中の変更があればその値 */
export const usePendingBodyValue = (doc: DocumentResponse, path: string): string | undefined => {
  const edits = usePendingEdits(doc.source);
  const value = edits.find((item) => item.key === keyOf(doc, path))?.values[path];
  return typeof value === "string" ? value : undefined;
};

/** 書き換えた YAML を種類のスキーマで変換したプレビューの Markdown */
export const previewQueryOptions = (doc: DocumentResponse, content: string) =>
  queryOptions({
    queryKey: ["view", "preview", doc.source, doc.path, content],
    queryFn: ({ signal }) =>
      apiClient<{ markdown: string }>(`/_api/sources/${encodeURIComponent(doc.source)}/preview`, {
        method: "POST",
        body: JSON.stringify({ path: doc.path, content }),
        signal,
      }),
    placeholderData: keepPreviousData,
  });
