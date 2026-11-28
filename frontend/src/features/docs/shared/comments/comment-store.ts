import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { legacyKeyStorage } from "@/shared/stores/legacy-key-storage";

/** 本文の文字列に付けた 1 件のコメント */
export type DocComment = {
  id: string;
  /** `{source}@{ref}:{path}` */
  docId: string;
  source: string;
  ref: string | null;
  path: string;
  docTitle: string;
  headings: string[];
  quote: string;
  prefix: string;
  suffix: string;
  body: string;
  selected: boolean;
  createdAt: string;
};

export type NewComment = Omit<DocComment, "id" | "selected" | "createdAt">;

type CommentState = {
  comments: DocComment[];
  add: (input: NewComment) => DocComment;
  update: (id: string, body: string) => void;
  remove: (id: string) => { comment: DocComment; index: number } | null;
  setSelected: (id: string | null, selected: boolean) => void;
  restore: (comment: DocComment, index: number) => void;
};

/** 文書のコメントの `docId`（配信元・リビジョン・パス） */
export const docIdOf = (doc: {
  source: string;
  ref?: string | null;
  path: string;
}) => `${doc.source}@${doc.ref ?? ""}:${doc.path}`;

/** `docId` のコメントを、mdmark の `commentStore.load` が返却する構造で追加した順に返却する */
export const commentsOf = (comments: DocComment[], docId: string) =>
  comments
    .filter((comment) => comment.docId === docId)
    .map(({ id, quote, prefix, suffix, body }) => ({
      id,
      quote,
      prefix,
      suffix,
      body,
    }));

/** このブラウザのタブで溜めたコメントの保存先（`sessionStorage`） */
export const useCommentStore = create<CommentState>()(
  persist(
    (set, get) => ({
      comments: [],
      add: (input) => {
        const comment: DocComment = {
          ...input,
          id: crypto.randomUUID(),
          selected: true,
          createdAt: new Date().toISOString(),
        };
        set((state) => ({ comments: [...state.comments, comment] }));
        return comment;
      },
      update: (id, body) =>
        set((state) => ({
          comments: state.comments.map((item) =>
            item.id === id ? { ...item, body } : item,
          ),
        })),
      remove: (id) => {
        const index = get().comments.findIndex((item) => item.id === id);
        if (index < 0) return null;
        const comment = get().comments[index];
        set((state) => ({
          comments: state.comments.filter((item) => item.id !== id),
        }));
        return { comment, index };
      },
      setSelected: (id, selected) =>
        set((state) => ({
          comments: state.comments.map((item) =>
            id === null || item.id === id ? { ...item, selected } : item,
          ),
        })),
      restore: (comment, index) =>
        set((state) => {
          if (state.comments.some((item) => item.id === comment.id)) return state;
          const at = Math.min(Math.max(index, 0), state.comments.length);
          return {
            comments: [
              ...state.comments.slice(0, at),
              comment,
              ...state.comments.slice(at),
            ],
          };
        }),
    }),
    {
      name: "dev-docs:v1:doc-view:comments",
      version: 1,
      storage: createJSONStorage(() =>
        legacyKeyStorage(() => sessionStorage, "dev-docs:comments"),
      ),
      partialize: (state) => ({ comments: state.comments }),
    },
  ),
);
