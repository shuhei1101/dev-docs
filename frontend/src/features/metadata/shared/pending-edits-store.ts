import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { Edit } from "@/shared/api/generated/model";

/** 編集中の変更 1 件。直コミットの `edits[]` と、パネルに出す値を持つ */
export type PendingEdit = {
  /** `{kind}:{docId}:{op}` */
  key: string;
  kind: "terms" | "aliases" | "tags" | "rules" | "files";
  op: "update" | "add" | "delete";
  docId: string;
  /** `update`・`delete` は行の `docKind`、`add` は種類の `createKind` */
  docKind: string;
  expectedVersion: string | null;
  values: Record<string, string | string[]>;
  /** 変更前の値（パネルの `{変更前} → {変更後}`） */
  before: Record<string, string | string[]>;
  /** `{種類の title}: {行の名前}` */
  label: string;
};

type PendingEditsState = {
  bySource: Record<string, PendingEdit[]>;
  upsert: (source: string, edit: PendingEdit) => void;
  remove: (source: string, key: string) => void;
  clear: (source: string) => void;
};

const sameValue = (a: string | string[] | undefined, b: string | string[] | undefined): boolean =>
  JSON.stringify(a ?? "") === JSON.stringify(b ?? "");

/** `update` で値が全て変更前と同じか */
const isUnchanged = (edit: PendingEdit): boolean =>
  edit.op === "update" &&
  Object.entries(edit.values).every(([column, value]) => sameValue(value, edit.before[column]));

/** 配信元ごとの編集中の変更（このブラウザのタブの `sessionStorage`） */
export const usePendingEditsStore = create<PendingEditsState>()(
  persist(
    (set) => ({
      bySource: {},
      upsert: (source, edit) =>
        set((state) => {
          const current = state.bySource[source] ?? [];
          const index = current.findIndex((item) => item.key === edit.key);
          const next =
            index === -1
              ? [...current, edit]
              : current.map((item, position) => (position === index ? edit : item));
          // 元の値に戻した修正は変更から除く
          const kept = isUnchanged(edit) ? next.filter((item) => item.key !== edit.key) : next;
          return { bySource: { ...state.bySource, [source]: kept } };
        }),
      remove: (source, key) =>
        set((state) => ({
          bySource: {
            ...state.bySource,
            [source]: (state.bySource[source] ?? []).filter((item) => item.key !== key),
          },
        })),
      clear: (source) =>
        set((state) => ({
          bySource: Object.fromEntries(
            Object.entries(state.bySource).filter(([id]) => id !== source),
          ),
        })),
    }),
    {
      name: "dev-docs:pending-edits",
      version: 1,
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ bySource: state.bySource }),
    },
  ),
);

const EMPTY: PendingEdit[] = [];

/** 配信元の編集中の変更 */
export const usePendingEdits = (source: string): PendingEdit[] =>
  usePendingEditsStore((state) => state.bySource[source] ?? EMPTY);

/** 編集中の変更を直コミットの `edits` にする（`before`・`label` と、`add` の `expectedVersion` を除く） */
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
    return edit.op === "add" ? base : { ...base, expectedVersion: edit.expectedVersion };
  });
