import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { legacyKeyStorage } from "@/shared/stores/legacy-key-storage";

export type ColorScheme = "light" | "dark" | "system";

/** 文書の画面のサイドバーの幅（CSS px）。既定は 15rem */
export const SIDEBAR_WIDTH = { min: 192, max: 480, initial: 240 } as const;

/** サイドバーの幅を最小・最大の間に収める */
export const clampSidebarWidth = (width: number): number =>
  Math.min(SIDEBAR_WIDTH.max, Math.max(SIDEBAR_WIDTH.min, Math.round(width)));

type PreferencesState = {
  colorScheme: ColorScheme;
  singleKeyShortcuts: boolean;
  sidebarOpen: boolean;
  sidebarWidth: number;
  setColorScheme: (value: ColorScheme) => void;
  setSingleKeyShortcuts: (value: boolean) => void;
  setSidebarOpen: (value: boolean) => void;
  setSidebarWidth: (value: number) => void;
};

/** ブラウザに保存する画面の設定（明暗・1 文字のショートカット・文書の画面のサイドバーの開閉と幅） */
export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      colorScheme: "system",
      singleKeyShortcuts: true,
      sidebarOpen: true,
      sidebarWidth: SIDEBAR_WIDTH.initial,
      setColorScheme: (value) => set({ colorScheme: value }),
      setSingleKeyShortcuts: (value) => set({ singleKeyShortcuts: value }),
      setSidebarOpen: (value) => set({ sidebarOpen: value }),
      setSidebarWidth: (value) =>
        set({ sidebarWidth: clampSidebarWidth(value) }),
    }),
    {
      name: "dev-docs:v1:shared:preferences",
      version: 1,
      storage: createJSONStorage(() =>
        legacyKeyStorage(() => localStorage, "dev-docs:preferences"),
      ),
    },
  ),
);
