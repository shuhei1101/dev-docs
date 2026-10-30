import { useRouter } from "@tanstack/react-router";
import { ArrowLeft, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { SourceDeleteDialog } from "@/features/settings/settings/components/source-delete-dialog";
import { SourceEditDialog } from "@/features/settings/settings/components/source-edit-dialog";
import { SourceSkeleton } from "@/features/settings/settings/components/source-skeleton";
import { SourceTable } from "@/features/settings/settings/components/source-table";
import type { SettingsSourceRow } from "@/shared/api/generated/model";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { SkipLink } from "@/shared/components/skip-link";
import { Topbar } from "@/shared/components/topbar/topbar";
import { Button, buttonVariants } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import { useDelayedFlag } from "@/shared/hooks/use-delayed-flag";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { cn } from "@/shared/lib/utils";
import { useLastDocStore } from "@/shared/stores/last-doc";
import { usePreferencesStore } from "@/shared/stores/preferences";

const LOADING_DELAY_MS = 1000;

type Dialog =
  | { kind: "edit"; index: number | null }
  | { kind: "remove"; index: number }
  | null;

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

type SourceListProps = {
  sources: SettingsSourceRow[] | undefined;
  loading: boolean;
  onEdit: (index: number) => void;
  onRemove: (index: number) => void;
};

/** 配信元の一覧。取得を待つ間は読み込み中の表示、0 件のときは配信元が無いことの表示を出す */
const SourceList = ({ sources, loading, onEdit, onRemove }: SourceListProps) => {
  if (sources === undefined) return loading ? <SourceSkeleton /> : null;
  if (sources.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">配信元はありません。</p>
    );
  }
  return <SourceTable sources={sources} onEdit={onEdit} onRemove={onRemove} />;
};

/** 設定画面。端末の設定の配信元を状態とともに並べ、追加・編集・削除をダイアログで行う */
export const SettingsScreen = () => {
  const query = useSettingsGetSettingsSources();
  const sources = query.data?.sources;
  const loading = useDelayedFlag(query.isPending, LOADING_DELAY_MS);
  const router = useRouter();
  const lastDoc = useLastDocStore((state) => state.href);
  const backTo = lastDoc ?? "/";
  const {
    colorScheme,
    singleKeyShortcuts,
    setColorScheme,
    setSingleKeyShortcuts,
  } = usePreferencesStore();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const serving = (sources ?? []).some(
    (item) => item.status === "serving" && item.id,
  );

  useShortcut("help", () => setHelpOpen(true), {
    enabled: !helpOpen && dialog === null,
  });
  useEffect(() => {
    document.title = "設定 | dev-docs";
  }, []);

  return (
    <div className="min-h-screen">
      <SkipLink />
      <Topbar
        screen="settings"
        colorScheme={colorScheme}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <main id="main" tabIndex={-1} className="mx-auto max-w-4xl space-y-8 p-6">
        {serving && (
          <a
            href={backTo}
            onClick={(event) => {
              event.preventDefault();
              router.history.push(backTo);
            }}
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
          >
            <ArrowLeft />
            文書の画面に戻る
          </a>
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
          <SourceList
            sources={sources}
            loading={loading}
            onEdit={(index) => setDialog({ kind: "edit", index })}
            onRemove={(index) => setDialog({ kind: "remove", index })}
          />
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
      {sources && dialog?.kind === "edit" && (
        <SourceEditDialog
          key={dialog.index ?? "new"}
          open
          onOpenChange={(open) => !open && setDialog(null)}
          sources={sources}
          index={dialog.index}
        />
      )}
      {sources && dialog?.kind === "remove" && (
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
