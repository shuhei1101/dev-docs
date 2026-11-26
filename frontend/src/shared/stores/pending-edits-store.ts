import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { Edit } from "@/shared/api/generated/model";

/** 変更の 1 つの列・項目の値（表の項目は行ごとの列の値） */
export type EditValue = string | string[] | Array<Record<string, string>>;

/** 編集中の変更 1 件。直コミットの `edits[]` と、パネルに出す値を持つ */
export type PendingEdit = {
  /** `{kind}:{docId}:{op}`（本文の変更は `body:{docId}:{項目のパス}`） */
  key: string;
  /** `body` は文書の画面で編集した本文の変更 */
  kind: "terms" | "aliases" | "tags" | "rules" | "files" | "body";
  op: "update" | "add" | "delete";
  docId: string;
  /** `update`・`delete` は行の `docKind`、`add` は種類の `createKind` */
  docKind: string;
  expectedVersion: string | null;
  /** 文書のパス（行の `docPath`、本文の変更は `edit.filePath`。`add` は `null`） */
  docPath: string | null;
  values: Record<string, EditValue>;
  /** 変更前の値（パネルの `{変更前} → {変更後}`） */
  before: Record<string, EditValue>;
  /** `{種類の title}: {行の名前}`（本文の変更は `{項目の名前}（{ファイルのパス}）`） */
  label: string;
};

/** 種類 → 行の ID → 列のキーごとの値（再取得したメタデータ） */
export type LatestValues = Record<string, Record<string, Record<string, string | string[]>>>;

/** 文書の ID → 項目のパス（`@file` を含む）ごとの値（再取得した文書の `edit`） */
export type LatestBodies = Record<string, Record<string, EditValue>>;

type PendingEditsState = {
  bySource: Record<string, PendingEdit[]>;
  /** 配信元ごとの編集を始めたときのコミット（メタデータの取得の `baseCommit`） */
  baseCommitBySource: Record<string, string>;
  upsert: (source: string, edit: PendingEdit, baseCommit: string) => void;
  remove: (source: string, key: string) => void;
  clear: (source: string) => void;
  rebase: (source: string, baseCommit: string, latest: LatestValues, latestBody: LatestBodies) => PendingEdit[];
};

const sameValue = (a: EditValue | undefined, b: EditValue | undefined): boolean =>
  JSON.stringify(a ?? "") === JSON.stringify(b ?? "");

/** `update` で値が全て変更前と同じか */
const isUnchanged = (edit: PendingEdit): boolean =>
  edit.op === "update" &&
  Object.entries(edit.values).every(([column, value]) => sameValue(value, edit.before[column]));

/** 再取得した値のどれかが変更前の値と違う `update` か（行・文書・項目が無いものも含む） */
const isStale = (edit: PendingEdit, latest: LatestValues, latestBody: LatestBodies): boolean => {
  if (edit.op !== "update") return false;
  const row: Record<string, EditValue> | undefined =
    edit.kind === "body" ? latestBody[edit.docId] : latest[edit.kind]?.[edit.docId];
  if (row === undefined) return true;
  return Object.keys(edit.values).some((column) => !sameValue(row[column], edit.before[column]));
};

/** 変更の件数に合わせて、配信元の編集を始めたときのコミットを残すか除く */
const withBaseCommit = (
  baseCommits: Record<string, string>,
  source: string,
  edits: PendingEdit[],
  baseCommit: string,
): Record<string, string> => {
  // 変更が無くなった: 記録を除く
  if (edits.length === 0) {
    return Object.fromEntries(Object.entries(baseCommits).filter(([id]) => id !== source));
  }
  // 最初の 1 件: そのときのコミットを記録する（2 件目以降は変えない）
  return baseCommits[source] === undefined ? { ...baseCommits, [source]: baseCommit } : baseCommits;
};

const without = <T,>(record: Record<string, T>, source: string): Record<string, T> =>
  Object.fromEntries(Object.entries(record).filter(([id]) => id !== source));

/** 配信元ごとの編集中の変更（このブラウザのタブの `sessionStorage`） */
export const usePendingEditsStore = create<PendingEditsState>()(
  persist(
    (set, get) => ({
      bySource: {},
      baseCommitBySource: {},
      upsert: (source, edit, baseCommit) =>
        set((state) => {
          const current = state.bySource[source] ?? [];
          const index = current.findIndex((item) => item.key === edit.key);
          const next =
            index === -1
              ? [...current, edit]
              : current.map((item, position) => (position === index ? edit : item));
          // 元の値に戻した修正は変更から除く
          const kept = isUnchanged(edit) ? next.filter((item) => item.key !== edit.key) : next;
          return {
            bySource: { ...state.bySource, [source]: kept },
            baseCommitBySource: withBaseCommit(state.baseCommitBySource, source, kept, baseCommit),
          };
        }),
      remove: (source, key) =>
        set((state) => {
          const kept = (state.bySource[source] ?? []).filter((item) => item.key !== key);
          return {
            bySource: { ...state.bySource, [source]: kept },
            baseCommitBySource:
              kept.length === 0 ? without(state.baseCommitBySource, source) : state.baseCommitBySource,
          };
        }),
      clear: (source) =>
        set((state) => ({
          bySource: without(state.bySource, source),
          baseCommitBySource: without(state.baseCommitBySource, source),
        })),
      rebase: (source, baseCommit, latest, latestBody) => {
        const current = get().bySource[source] ?? [];
        const dropped = current.filter((edit) => isStale(edit, latest, latestBody));
        const kept = current.filter((edit) => !isStale(edit, latest, latestBody));
        set((state) => ({
          bySource: { ...state.bySource, [source]: kept },
          baseCommitBySource:
            kept.length === 0
              ? without(state.baseCommitBySource, source)
              : { ...state.baseCommitBySource, [source]: baseCommit },
        }));
        return dropped;
      },
    }),
    {
      name: "dev-docs:pending-edits",
      version: 2,
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ bySource: state.bySource, baseCommitBySource: state.baseCommitBySource }),
      // version 1 の変更は編集を始めたときのコミットを持たないため捨てる
      migrate: () => ({ bySource: {}, baseCommitBySource: {} }),
    },
  ),
);

const EMPTY: PendingEdit[] = [];

/** 配信元の編集中の変更 */
export const usePendingEdits = (source: string): PendingEdit[] =>
  usePendingEditsStore((state) => state.bySource[source] ?? EMPTY);

/** 配信元の編集を始めたときのコミット */
export const useBaseCommit = (source: string): string | undefined =>
  usePendingEditsStore((state) => state.baseCommitBySource[source]);

/** 編集中の変更を直コミットの `edits` にする（`before`・`label`、`add` の `expectedVersion`、`update` 以外の `docPath` を除く） */
export const toCommitEdits = (edits: PendingEdit[]): Edit[] =>
  edits.map((edit) => {
    const base = {
      key: edit.key,
      kind: edit.kind,
      op: edit.op,
      docId: edit.docId,
      docKind: edit.docKind,
      values: edit.values,
    };
    if (edit.op === "add") return base;
    if (edit.op === "delete") return { ...base, expectedVersion: edit.expectedVersion };
    return { ...base, expectedVersion: edit.expectedVersion, docPath: edit.docPath };
  });
