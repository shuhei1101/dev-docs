import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

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
  remove: (id: string) => void;
  setSelected: (id: string | null, selected: boolean) => void;
};

/** `docId` のコメントを、mdmark の `commentStore.load` が返す形で追加した順に返す */
export const commentsOf = (comments: DocComment[], docId: string) =>
  comments
    .filter((comment) => comment.docId === docId)
    .map(({ id, quote, prefix, suffix, body }) => ({ id, quote, prefix, suffix, body }));

/** このブラウザのタブで溜めたコメントの置き場所（`sessionStorage`） */
export const useCommentStore = create<CommentState>()(
  persist(
    (set) => ({
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
          comments: state.comments.map((item) => (item.id === id ? { ...item, body } : item)),
        })),
      remove: (id) => set((state) => ({ comments: state.comments.filter((item) => item.id !== id) })),
      setSelected: (id, selected) =>
        set((state) => ({
          comments: state.comments.map((item) =>
            id === null || item.id === id ? { ...item, selected } : item,
          ),
        })),
    }),
    {
      name: "dev-docs:comments",
      version: 1,
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ comments: state.comments }),
    },
  ),
);
