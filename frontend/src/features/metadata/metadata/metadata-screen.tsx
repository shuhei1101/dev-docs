import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { CircleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { NotFoundScreen } from "@/features/docs/not-found/not-found-screen";
import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import { servingSources, unservedSources } from "@/features/docs/shared/serving-sources";
import { MetadataTable, rowElementId } from "@/features/metadata/metadata/metadata-table";
import { PendingPanel } from "@/shared/components/pending-panel/pending-panel";
import { type PendingEdit, useBaseCommit, usePendingEdits } from "@/shared/stores/pending-edits-store";
import { getMetadataGetMetadataQueryOptions } from "@/shared/api/generated/metadata/metadata";
import type { MetadataResponse } from "@/shared/api/generated/model";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import {
  ProjectIndexUnreachableAlert,
  toProjectIndexUnreachable,
} from "@/shared/components/project-index-unreachable";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { SkipLink } from "@/shared/components/skip-link";
import { Topbar } from "@/shared/components/topbar/topbar";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { AppError } from "@/shared/core/app-error";
import { useDelayedFlag } from "@/shared/hooks/use-delayed-flag";
import { useLeaveGuard } from "@/shared/hooks/use-leave-guard";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { usePreferencesStore } from "@/shared/stores/preferences";

const LOADING_DELAY_MS = 1000;
const NOT_FOUND = 404;
const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

type MetadataSearch = { tab?: string; q?: string; panel?: "edits" };

/** メタデータの取得を待つ間の読み込み中の表示 */
const MetadataSkeleton = () => (
  <div aria-busy="true" aria-label="メタデータを読み込んでいます" className="space-y-3">
    <Skeleton className="h-8 w-2/3" />
    <Skeleton className="h-48 w-full" />
  </div>
);

/** project-index から受け取れないとき以外の取得の失敗 */
const FetchFailed = ({ error, onReload }: { error: unknown; onReload: () => void }) => {
  const detail =
    error instanceof AppError ? (error.problem?.detail ?? `HTTP ${error.status}`) : String(error);
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden="true" />
      <AlertTitle>メタデータを取得できませんでした</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{detail}</p>
        <Button variant="outline" size="sm" onClick={onReload}>
          再読み込み
        </Button>
      </AlertDescription>
    </Alert>
  );
};

type KindTabsProps = {
  source: string;
  data: MetadataResponse;
  tab: string;
  query: string;
  onTabChange: (tab: string) => void;
};

/** 種類のタブと、選んだ種類の表 */
const KindTabs = ({ source, data, tab, query, onTabChange }: KindTabsProps) => (
  <Tabs value={tab} onValueChange={(value) => onTabChange(String(value))} className="min-w-0 flex-col">
    <TabsList className="h-auto w-full flex-wrap justify-start">
      {data.kinds.map((kind) => (
        <TabsTrigger key={kind.id} value={kind.id} className="h-7 flex-none">
          {kind.title}
          <span className="ml-1 text-xs text-muted-foreground">{kind.served ? kind.rows.length : "-"}</span>
        </TabsTrigger>
      ))}
    </TabsList>
    {data.kinds.map((kind) => (
      <TabsContent key={kind.id} value={kind.id} className="min-w-0">
        <MetadataTable source={source} kind={kind} query={query} baseCommit={data.baseCommit ?? ""} />
      </TabsContent>
    ))}
  </Tabs>
);

type Props = { source: string };

/** 1 つの配信元のメタデータを、種類ごとの表で参照・編集する画面 */
export const MetadataScreen = ({ source }: Props) => {
  const search: MetadataSearch = useSearch({ strict: false });
  const navigate = useNavigate();
  // 編集中の変更があるときは、記録した編集を始めたときのコミットの内容を参照する
  const baseCommit = useBaseCommit(source);
  const metadata = useQuery(
    getMetadataGetMetadataQueryOptions(source, baseCommit === undefined ? undefined : { ref: baseCommit }),
  );
  const settings = useSettingsGetSettingsSources().data;
  const edits = usePendingEdits(source);
  const { colorScheme, setColorScheme, singleKeyShortcuts } = usePreferencesStore();
  const loading = useDelayedFlag(metadata.isPending, LOADING_DELAY_MS);
  const [searchOpen, setSearchOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const idle = !searchOpen && !helpOpen;
  useShortcut("search", () => setSearchOpen(true), { enabled: idle });
  useShortcut("help", () => setHelpOpen(true), { enabled: idle });
  // 編集中の変更は sessionStorage に残るので、タブを閉じる・再読み込みだけ警告する
  useLeaveGuard(edits.length > 0);
  // 移動先の変更（描いた後に行の DOM を探す）と、移動を押した回数
  const locating = useRef<PendingEdit | null>(null);
  const [locateCount, setLocateCount] = useState(0);

  const tab = search.tab ?? metadata.data?.kinds[0]?.id ?? "terms";
  const query = search.q ?? "";
  const panelOpen = search.panel === "edits";
  const setSearch = (next: MetadataSearch) =>
    void navigate({
      to: "/$source/_metadata",
      params: { source },
      search: { ...search, ...next },
      replace: true,
    });

  useEffect(() => {
    document.title = `メタデータ | ${source} | dev-docs`;
  }, [source]);

  // 変更の行へ移動: タブを描いた後に、行の DOM へスクロールしてフォーカスする
  useEffect(() => {
    const target = locating.current;
    if (target === null || metadata.data === undefined) return;
    const element = document.getElementById(rowElementId(target.kind, target.docId));
    if (element === null) return;
    element.scrollIntoView?.({ block: "center" });
    element.focus();
    locating.current = null;
  }, [locateCount, metadata.data, tab]);

  const locate = (edit: PendingEdit) => {
    // 文書の本文の変更: その文書を編集の表示で開き、レビュー中のパネルを開いたままにする
    if (edit.kind === "body" && edit.docPath !== null) {
      const mode = Object.keys(edit.values).includes("@file") ? "file" : "fields";
      void navigate({
        to: "/$source/$",
        params: { source, _splat: edit.docPath },
        search: { edit: mode, panel: "edits" },
      });
      return;
    }
    locating.current = edit;
    setSearch({ tab: edit.kind, q: undefined });
    setLocateCount((count) => count + 1);
  };

  if (metadata.error instanceof AppError && metadata.error.status === NOT_FOUND) {
    return <NotFoundScreen data={metadata.error.problem} />;
  }
  const unreachable = toProjectIndexUnreachable(metadata.error);

  return (
    <div className="min-h-screen bg-background">
      <SkipLink />
      <Topbar
        screen="metadata"
        currentSource={source}
        sources={servingSources(settings)}
        pendingEditCount={edits.length}
        colorScheme={colorScheme}
        onSourceSelect={(id) => void navigate({ to: "/$source/_metadata", params: { source: id } })}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
        onPendingPanelToggle={() => setSearch({ panel: panelOpen ? undefined : "edits" })}
        onSearchOpen={() => setSearchOpen(true)}
      />
      <main id="main" tabIndex={-1} className="flex min-w-0 flex-col gap-4 p-4">
        <h1 className="text-2xl font-semibold">{source} のメタデータ</h1>
        <div className="flex max-w-sm flex-col gap-1.5">
          <Label htmlFor="metadata-filter">絞り込み</Label>
          <Input
            id="metadata-filter"
            type="search"
            placeholder="用語・パス・タグ"
            value={query}
            onChange={(event) => setSearch({ q: event.target.value === "" ? undefined : event.target.value })}
          />
        </div>
        {loading && <MetadataSkeleton />}
        {unreachable !== null && (
          <ProjectIndexUnreachableAlert
            kind={unreachable.kind}
            address={unreachable.address}
            reason={unreachable.reason}
            onReload={() => void metadata.refetch()}
          />
        )}
        {metadata.isError && unreachable === null && (
          <FetchFailed error={metadata.error} onReload={() => void metadata.refetch()} />
        )}
        {metadata.data !== undefined && (
          <KindTabs
            source={source}
            data={metadata.data}
            tab={tab}
            query={query}
            onTabChange={(next) => setSearch({ tab: next })}
          />
        )}
      </main>
      <PendingPanel
        source={source}
        branch={metadata.data?.branch ?? null}
        open={panelOpen}
        onOpenChange={(open) => setSearch({ panel: open ? "edits" : undefined })}
        onLocate={locate}
      />
      <SearchDialog
        open={searchOpen}
        onOpenChange={setSearchOpen}
        source={source}
        sources={servingSources(settings).map((item) => item.id)}
        unavailable={unservedSources(settings)}
        onResultSelect={(path, resultSource) =>
          void navigate({ to: "/$source/$", params: { source: resultSource, _splat: path } })
        }
      />
      <ShortcutDialog
        open={helpOpen}
        onOpenChange={setHelpOpen}
        screen="metadata"
        singleKey={singleKeyShortcuts}
      />
    </div>
  );
};
