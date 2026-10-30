import { useHotkeys } from "@tanstack/react-hotkeys";

import { SHORTCUTS, type ShortcutDef, type ShortcutId } from "@/shared/core/shortcuts";
import { usePreferencesStore } from "@/shared/stores/preferences";

/** `SHORTCUTS` の定義のキーを受け、操作を呼ぶ。1 文字のキーは設定がオフのときと入力欄では受けない */
export const useShortcut = (
  id: ShortcutId,
  handler: () => void,
  options: { enabled?: boolean } = {},
): void => {
  const singleKeyOn = usePreferencesStore((state) => state.singleKeyShortcuts);
  const def = (SHORTCUTS as readonly ShortcutDef[]).find((item) => item.id === id);
  const enabled = options.enabled ?? true;
  useHotkeys(
    (def?.hotkeys ?? []).map((hotkey) => ({
      hotkey: hotkey as never,
      callback: handler,
      options: {
        enabled: enabled && (singleKeyOn || !def?.singleKey.includes(hotkey)),
        ignoreInputs: def?.singleKey.includes(hotkey) ? true : "auto",
        preventDefault: true,
      },
    })),
  );
};
