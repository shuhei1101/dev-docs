import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useState } from "react";

import { DocMain } from "@/features/docs/doc-view/components/doc-main";
import { DocSidebar } from "@/features/docs/doc-view/components/doc-sidebar";
import { DocTabs } from "@/features/docs/doc-view/components/doc-tabs";
import { MarkdownFieldPanel } from "@/features/docs/doc-view/components/markdown-field-panel";
import { SidebarDrawer } from "@/features/docs/doc-view/components/sidebar-drawer";
import { SidebarResizer } from "@/features/docs/doc-view/components/sidebar-resizer";
import { SidebarToggle } from "@/features/docs/doc-view/components/sidebar-toggle";
import { useDocNavigation } from "@/features/docs/doc-view/hooks/use-doc-navigation";
import { useLocating } from "@/features/docs/doc-view/hooks/use-locating";
import { useDocScreenEffects } from "@/features/docs/doc-view/hooks/use-doc-screen-effects";
import { docEditOf } from "@/features/docs/doc-view/edit";
import { findActivePage, pageTitle } from "@/features/docs/doc-view/nav";
import {
  baseMarkdownQueryOptions,
  documentQueryOptions,
} from "@/features/docs/doc-view/queries";
import type { DocEditMode, DocViewSearch } from "@/features/docs/doc-view/search";
import { CommentPanel } from "@/features/docs/shared/comments/comment-panel";
import {
  docIdOf,
  useCommentStore,
} from "@/features/docs/shared/comments/comment-store";
import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import {
  servingSources,
  unservedSources,
} from "@/features/docs/shared/serving-sources";
import { PendingPanel } from "@/shared/components/pending-panel/pending-panel";
import { type PendingEdit, usePendingEdits } from "@/shared/stores/pending-edits-store";
import type { EditBlock, NavTab } from "@/shared/api/generated/model";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import { useViewListRefs } from "@/shared/api/generated/view/view";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { SkipLink } from "@/shared/components/skip-link";
import { Topbar } from "@/shared/components/topbar/topbar";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { usePreferencesStore } from "@/shared/stores/preferences";

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

type BaseDocument = { markdown: string; tableKeys: string[] } | null;

/** 差分を表示しているときに、本文の強調に指定する比較元（差分を表示していないか、比較元をまだ取っていなければ null） */
const diffBase = (
  doc: { diff?: unknown },
  base: BaseDocument | undefined,
): BaseDocument => (!doc.diff || base === undefined ? null : base);

type Panels = {
  search: boolean;
  help: boolean;
  drawer: boolean;
  comments: boolean;
  pending: boolean;
};

/** 文書の画面。トップバー・種類のタブ・サイドバー・本文・コメントのパネルを並べる */
export const DocViewScreen = () => {
  const params = useParams({ strict: false }) as {
    source: string;
    _splat?: string;
  };
  const search = useSearch({ strict: false }) as DocViewSearch;
  const { source } = params;

  const [panels, setPanels] = useState<Panels>({
    search: false,
    help: false,
    drawer: false,
    comments: false,
    // メタデータの画面から本文の変更へ移ったときは、編集中のパネルを開いたままにする
    pending: search.panel === "edits",
  });
  // 画面の横のパネルで編集する Markdown の文字列の項目
  const [markdownField, setMarkdownField] = useState<EditBlock | null>(null);
  const open = (name: keyof Panels, value = true) =>
    setPanels((prev) => ({ ...prev, [name]: value }));
  // 文書の無いタブを選んだとき（文書が変わったら戻す）
  const [empty, setEmpty] = useState<{ tab: NavTab; path: string } | null>(
    null,
  );

  const {
    colorScheme,
    singleKeyShortcuts,
    setColorScheme,
    sidebarOpen,
    sidebarWidth,
    setSidebarOpen,
    setSidebarWidth,
  } = usePreferencesStore();
  const commentCount = useCommentStore((state) => state.comments.length);
  const pendingEditCount = usePendingEdits(source).length;
  const navigate = useNavigate();

  const query = useSuspenseQuery(
    documentQueryOptions(source, params._splat ?? "", search),
  );
  const doc = query.data;
  const refs = useViewListRefs(source).data;
  const settings = useSettingsGetSettingsSources().data;
  const nav = useDocNavigation(source, doc.path, search, refs);
  const place = useLocating(docIdOf(doc), nav.locate);

  const edit = docEditOf(doc);
  const active = findActivePage(doc.tabs, doc.path, search.tab);
  const emptyTab = empty?.path === doc.path ? empty.tab : null;
  const baseMarkdown = useQuery(
    baseMarkdownQueryOptions(source, doc.path, doc.diff?.base ?? null),
  ).data;
  const base = diffBase(doc, baseMarkdown);

  useDocScreenEffects(pageTitle(active, source, emptyTab), source);
  const idle = !panels.search && !panels.help;
  useShortcut("search", () => open("search"), { enabled: idle });
  useShortcut("help", () => open("help"), { enabled: idle });

  const setEditMode = (mode: DocEditMode | undefined) =>
    void navigate({ to: ".", search: { ...search, edit: mode }, replace: true });

  /** 編集中の変更の行へ移動する（本文の変更はその文書の編集の表示、メタデータの変更はメタデータの画面） */
  const locateEdit = (edit: PendingEdit) => {
    if (edit.kind !== "body" || edit.docPath === null) {
      void navigate({ to: "/$source/_metadata", params: { source }, search: { panel: "edits", tab: edit.kind } });
      return;
    }
    const mode: DocEditMode = Object.keys(edit.values).includes("@file") ? "file" : "fields";
    void navigate({ to: "/$source/$", params: { source, _splat: edit.docPath }, search: { edit: mode } });
  };

  const sidebar = (onNavigate?: () => void) => (
    <DocSidebar
      tab={emptyTab ?? active.tab}
      source={source}
      currentPath={emptyTab ? null : doc.path}
      search={search}
      onNavigate={onNavigate}
    />
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <SkipLink />
      <Topbar
        screen="doc-view"
        sources={servingSources(settings)}
        currentSource={source}
        refs={refs}
        currentRef={doc.ref ?? undefined}
        commentCount={commentCount}
        pendingEditCount={pendingEditCount}
        colorScheme={colorScheme}
        onSourceSelect={nav.selectSource}
        onRefSelect={nav.selectRef}
        onCompareStart={nav.startCompare}
        onSearchOpen={() => open("search")}
        onCommentPanelToggle={() => open("comments", !panels.comments)}
        onPendingPanelToggle={() => open("pending", !panels.pending)}
        onSidebarOpen={() => open("drawer")}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <div className="shrink-0 bg-background px-3">
        <DocTabs
          tabs={doc.tabs}
          currentIndex={Math.max(0, doc.tabs.indexOf(active.tab))}
          source={source}
          search={search}
          onEmptyTab={(tab) => setEmpty({ tab, path: doc.path })}
        />
      </div>
      <div className="flex min-h-0 flex-1 px-4">
        {sidebarOpen ? (
          <>
            <div
              id="doc-sidebar"
              style={{ width: sidebarWidth }}
              className="hidden shrink-0 overflow-y-auto py-2 md:block"
            >
              <div className="flex justify-end">
                <SidebarToggle open onOpenChange={setSidebarOpen} />
              </div>
              {sidebar()}
            </div>
            <div className="mr-3 hidden md:flex">
              <SidebarResizer
                width={sidebarWidth}
                onWidthChange={setSidebarWidth}
              />
            </div>
          </>
        ) : (
          <div className="mr-3 hidden shrink-0 py-2 md:block">
            <SidebarToggle open={false} onOpenChange={setSidebarOpen} />
          </div>
        )}
        <div id="doc-scroll" className="min-w-0 flex-1 overflow-y-auto">
          <DocMain
            doc={doc}
            active={active}
            search={search}
            refs={refs}
            emptyTab={emptyTab}
            busy={query.isFetching}
            onCommentSaved={() => open("comments")}
            locating={place.locating}
            baseMarkdown={base}
            onLocated={place.onLocated}
            onRetry={() => void query.refetch()}
            onCompare={nav.compare}
            onClearDiff={nav.clearDiff}
            onEditModeChange={setEditMode}
            onMarkdownFieldOpen={setMarkdownField}
          />
        </div>
      </div>
      <SidebarDrawer
        open={panels.drawer}
        onOpenChange={(value) => open("drawer", value)}
      >
        {sidebar(() => open("drawer", false))}
      </SidebarDrawer>
      <SearchDialog
        open={panels.search}
        onOpenChange={(value) => open("search", value)}
        source={source}
        ref={doc.ref ?? undefined}
        sources={servingSources(settings).map((item) => item.id)}
        unavailable={unservedSources(settings)}
        onResultSelect={nav.openSearchResult}
      />
      <ShortcutDialog
        open={panels.help}
        onOpenChange={(value) => open("help", value)}
        screen="doc-view"
        singleKey={singleKeyShortcuts}
      />
      <PendingPanel
        source={source}
        branch={null}
        open={panels.pending}
        onOpenChange={(value) => open("pending", value)}
        onLocate={locateEdit}
      />
      {edit !== null && (
        <MarkdownFieldPanel
          source={source}
          docId={docIdOf(doc)}
          edit={edit}
          block={markdownField}
          onClose={() => setMarkdownField(null)}
        />
      )}
      <CommentPanel
        open={panels.comments}
        onOpenChange={(value) => open("comments", value)}
        github={doc.github ?? null}
        onLocate={place.locate}
      />
    </div>
  );
};
