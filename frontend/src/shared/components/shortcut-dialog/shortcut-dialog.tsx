import { type ScreenId, shortcutsFor } from "@/shared/core/shortcuts";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Kbd } from "@/shared/components/ui/kbd";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  screen: ScreenId;
  singleKey: boolean;
};

const IS_MAC =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.platform);

/** TanStack Hotkeys の書き方を画面に出すキーにする（`Shift+/` は `?`） */
const display = (hotkey: string): string[] =>
  hotkey === "Shift+/"
    ? ["?"]
    : hotkey
        .split("+")
        .map((key) => (key === "Mod" ? (IS_MAC ? "⌘" : "Ctrl") : key));

/** 画面で使えるキーを並べるダイアログ */
export const ShortcutDialog = ({
  open,
  onOpenChange,
  screen,
  singleKey,
}: Props) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>キーボードのショートカット</DialogTitle>
        <DialogDescription>この画面で使えるキーです。</DialogDescription>
      </DialogHeader>
      <ul className="space-y-2">
        {shortcutsFor(screen, singleKey).map(({ def, hotkeys }) => (
          <li
            key={def.id}
            className="flex items-center justify-between gap-4 text-sm"
          >
            <span>{def.label}</span>
            <span className="flex items-center gap-2">
              {hotkeys.map((hotkey) => (
                <span key={hotkey} className="flex items-center gap-0.5">
                  {display(hotkey).map((key) => (
                    <Kbd key={key}>{key}</Kbd>
                  ))}
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </DialogContent>
  </Dialog>
);
