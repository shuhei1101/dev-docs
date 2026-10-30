import { create } from "zustand";

type LastDocState = {
  /** 直前に開いていた文書の画面の URL（パスと search） */
  href: string | null;
  setHref: (href: string) => void;
};

/** 設定画面から文書の画面へ戻るために、直前に開いていた文書の画面を覚える */
export const useLastDocStore = create<LastDocState>()((set) => ({
  href: null,
  setHref: (href) => set({ href }),
}));
