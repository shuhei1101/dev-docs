import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ColorScheme = "light" | "dark" | "system";

type PreferencesState = {
  colorScheme: ColorScheme;
  singleKeyShortcuts: boolean;
  setColorScheme: (value: ColorScheme) => void;
  setSingleKeyShortcuts: (value: boolean) => void;
};

/** ブラウザに保存する画面の設定（明暗・1 文字のショートカット） */
export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      colorScheme: "system",
      singleKeyShortcuts: true,
      setColorScheme: (value) => set({ colorScheme: value }),
      setSingleKeyShortcuts: (value) => set({ singleKeyShortcuts: value }),
    }),
    { name: "dev-docs:preferences", version: 1 },
  ),
);
