import {
  type UseSuspenseQueryOptions,
  useSuspenseQuery,
} from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { SourceDeleteDialog } from "@/features/settings/settings/components/source-delete-dialog";
import { SourceEditDialog } from "@/features/settings/settings/components/source-edit-dialog";
import { SourceTable } from "@/features/settings/settings/components/source-table";
import type { SettingsSourcesView } from "@/shared/api/generated/model";
import { getSettingsGetSettingsSourcesQueryOptions } from "@/shared/api/generated/settings/settings";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { Topbar } from "@/shared/components/topbar/topbar";
import { Button, buttonVariants } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { cn } from "@/shared/lib/utils";
import { usePreferencesStore } from "@/shared/stores/preferences";

type Dialog =
  | { kind: "edit"; index: number | null }
  | { kind: "remove"; index: number }
  | null;

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

/** 設定画面。端末の設定の配信元を状態とともに並べ、追加・編集・削除をダイアログで行う */
export const SettingsScreen = () => {
  const { sources } = useSuspenseQuery(
    getSettingsGetSettingsSourcesQueryOptions() as UseSuspenseQueryOptions<SettingsSourcesView>,
  ).data;
  const {
    colorScheme,
    singleKeyShortcuts,
    setColorScheme,
    setSingleKeyShortcuts,
  } = usePreferencesStore();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const serving = sources.some((item) => item.status === "serving" && item.id);

  useShortcut("help", () => setHelpOpen(true), {
    enabled: !helpOpen && dialog === null,
  });
  useEffect(() => {
    document.title = "設定 | dev-docs";
  }, []);

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-background focus:p-2"
      >
        本文へスキップ
      </a>
      <Topbar
        screen="settings"
        colorScheme={colorScheme}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <main id="main" tabIndex={-1} className="mx-auto max-w-4xl space-y-8 p-6">
        {serving && (
          <Link
            to="/"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
          >
            <ArrowLeft />
            文書の画面に戻る
          </Link>
        )}
        <h1 className="text-2xl font-semibold">設定</h1>
        <section aria-labelledby="sources-heading" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 id="sources-heading" className="text-lg font-semibold">
              配信元
            </h2>
            <Button
              size="sm"
              onClick={() => setDialog({ kind: "edit", index: null })}
            >
              <Plus />
              配信元を追加
            </Button>
          </div>
          {sources.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              配信元はありません。
            </p>
          ) : (
            <SourceTable
              sources={sources}
              onEdit={(index) => setDialog({ kind: "edit", index })}
              onRemove={(index) => setDialog({ kind: "remove", index })}
            />
          )}
        </section>
        <section aria-labelledby="keyboard-heading" className="space-y-3">
          <h2 id="keyboard-heading" className="text-lg font-semibold">
            キーボード
          </h2>
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label htmlFor="single-key">1 文字のショートカットを使う</Label>
              <p className="text-xs text-muted-foreground">
                / で検索、?
                でショートカットの一覧を開きます。この端末のブラウザに保存します。
              </p>
            </div>
            <Switch
              id="single-key"
              checked={singleKeyShortcuts}
              onCheckedChange={setSingleKeyShortcuts}
            />
          </div>
          <Button variant="outline" size="sm" onClick={() => setHelpOpen(true)}>
            ショートカットの一覧を開く
          </Button>
        </section>
      </main>
      {dialog?.kind === "edit" && (
        <SourceEditDialog
          key={dialog.index ?? "new"}
          open
          onOpenChange={(open) => !open && setDialog(null)}
          sources={sources}
          index={dialog.index}
        />
      )}
      {dialog?.kind === "remove" && (
        <SourceDeleteDialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          sources={sources}
          index={dialog.index}
        />
      )}
      <ShortcutDialog
        open={helpOpen}
        onOpenChange={setHelpOpen}
        screen="settings"
        singleKey={singleKeyShortcuts}
      />
    </div>
  );
};
