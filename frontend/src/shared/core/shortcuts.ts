export type ShortcutId = "search" | "help";
export type ScreenId = "doc-view" | "settings" | "not-found";

export type ShortcutDef = {
  id: ShortcutId;
  hotkeys: string[];
  label: string;
  /** `hotkeys` のうち 1 文字のキー（1 文字のショートカットを切ったときに受けない） */
  singleKey: string[];
  screens: ScreenId[];
};

export const SHORTCUTS = [
  {
    id: "search",
    hotkeys: ["Mod+K", "/"],
    label: "検索を開く",
    singleKey: ["/"],
    screens: ["doc-view", "not-found"],
  },
  {
    id: "help",
    hotkeys: ["Shift+/"],
    label: "ショートカットの一覧を開く",
    singleKey: ["Shift+/"],
    screens: ["doc-view", "settings", "not-found"],
  },
] as const satisfies readonly ShortcutDef[];

/** 画面と 1 文字のショートカットの設定に合う定義とキーを返す */
export const shortcutsFor = (
  screen: ScreenId,
  singleKey: boolean,
): { def: ShortcutDef; hotkeys: string[] }[] =>
  (SHORTCUTS as readonly ShortcutDef[])
    .filter((def) => def.screens.includes(screen))
    .map((def) => ({
      def,
      hotkeys: singleKey
        ? def.hotkeys
        : def.hotkeys.filter((key) => !def.singleKey.includes(key)),
    }))
    .filter(({ hotkeys }) => hotkeys.length > 0);
