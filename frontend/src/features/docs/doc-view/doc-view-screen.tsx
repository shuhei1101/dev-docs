import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useParams, useSearch } from "@tanstack/react-router";
import { useState } from "react";

import { DocMain } from "@/features/docs/doc-view/components/doc-main";
import { DocSidebar } from "@/features/docs/doc-view/components/doc-sidebar";
import { DocTabs } from "@/features/docs/doc-view/components/doc-tabs";
import { DocToc } from "@/features/docs/doc-view/components/doc-toc";
import { SidebarDrawer } from "@/features/docs/doc-view/components/sidebar-drawer";
import { useDocNavigation } from "@/features/docs/doc-view/hooks/use-doc-navigation";
import { useDocScreenEffects } from "@/features/docs/doc-view/hooks/use-doc-screen-effects";
import { findActivePage, pageTitle } from "@/features/docs/doc-view/nav";
import {
  baseMarkdownQueryOptions,
  documentQueryOptions,
} from "@/features/docs/doc-view/queries";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import { type TocItem, changedSections } from "@/features/docs/doc-view/toc";
import { CommentPanel } from "@/features/docs/shared/comments/comment-panel";
import {
  type DocComment,
  useCommentStore,
} from "@/features/docs/shared/comments/comment-store";
import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import { servingSources } from "@/features/docs/shared/serving-sources";
import type { NavTab } from "@/shared/api/generated/model";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import { useViewListRefs } from "@/shared/api/generated/view/view";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { SkipLink } from "@/shared/components/skip-link";
import { Topbar } from "@/shared/components/topbar/topbar";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { usePreferencesStore } from "@/shared/stores/preferences";

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

type Panels = {
  search: boolean;
  help: boolean;
  drawer: boolean;
  comments: boolean;
};

/** 文書の画面。トップバー・種類のタブ・サイドバー・本文・目次・コメントのパネルを並べる */
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
  });
  const open = (name: keyof Panels, value = true) =>
    setPanels((prev) => ({ ...prev, [name]: value }));
  // 文書の無いタブを選んだとき（文書が変わったら戻す）
  const [empty, setEmpty] = useState<{ tab: NavTab; path: string } | null>(
    null,
  );
  const [headings, setHeadings] = useState<TocItem[]>([]);
  // コメントのパネルで場所を選ばれたコメント（本文がその印まで移ったら戻す）
  const [locating, setLocating] = useState<DocComment | null>(null);

  const { colorScheme, singleKeyShortcuts, setColorScheme } =
    usePreferencesStore();
  const commentCount = useCommentStore((state) => state.comments.length);

  const query = useSuspenseQuery(
    documentQueryOptions(source, params._splat ?? "", search),
  );
  const doc = query.data;
  const refs = useViewListRefs(source).data;
  const settings = useSettingsGetSettingsSources().data;
  const nav = useDocNavigation(source, doc.path, search, refs);

  const active = findActivePage(doc.tabs, doc.path);
  const emptyTab = empty?.path === doc.path ? empty.tab : null;
  const baseMarkdown = useQuery(
    baseMarkdownQueryOptions(source, doc.path, doc.diff?.base ?? null),
  ).data;
  const changed =
    doc.diff && doc.markdown !== null && baseMarkdown !== undefined
      ? changedSections(doc.markdown, baseMarkdown)
      : undefined;

  useDocScreenEffects(pageTitle(active, source, emptyTab), source);
  const idle = !panels.search && !panels.help;
  useShortcut("search", () => open("search"), { enabled: idle });
  useShortcut("help", () => open("help"), { enabled: idle });

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
    <div className="min-h-screen">
      <SkipLink />
      <Topbar
        screen="doc-view"
        sources={servingSources(settings)}
        currentSource={source}
        refs={refs}
        currentRef={doc.ref ?? undefined}
        commentCount={commentCount}
        colorScheme={colorScheme}
        onSourceSelect={nav.selectSource}
        onRefSelect={nav.selectRef}
        onCompareStart={nav.startCompare}
        onSearchOpen={() => open("search")}
        onCommentPanelToggle={() => open("comments", !panels.comments)}
        onSidebarOpen={() => open("drawer")}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <div className="sticky top-12 z-20 bg-background px-3">
        <DocTabs
          tabs={doc.tabs}
          currentIndex={Math.max(0, doc.tabs.indexOf(active.tab))}
          source={source}
          search={search}
          onEmptyTab={(tab) => setEmpty({ tab, path: doc.path })}
        />
      </div>
      <div className="mx-auto flex max-w-screen-2xl gap-6 px-4">
        <div className="sticky top-24 hidden max-h-screen w-60 shrink-0 self-start overflow-y-auto py-4 md:block">
          {sidebar()}
        </div>
        <DocMain
          doc={doc}
          active={active}
          search={search}
          refs={refs}
          emptyTab={emptyTab}
          busy={query.isFetching}
          onHeadings={setHeadings}
          onCommentSaved={() => open("comments")}
          locating={locating}
          onLocated={() => setLocating(null)}
          onRetry={() => void query.refetch()}
          onCompare={nav.compare}
          onClearDiff={nav.clearDiff}
        />
        <div className="sticky top-24 hidden max-h-screen w-56 shrink-0 self-start overflow-y-auto py-6 xl:block">
          {!emptyTab && !doc.conversionError && (
            <DocToc items={headings} changed={changed} />
          )}
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
        onResultSelect={nav.openDoc}
      />
      <ShortcutDialog
        open={panels.help}
        onOpenChange={(value) => open("help", value)}
        screen="doc-view"
        singleKey={singleKeyShortcuts}
      />
      <CommentPanel
        open={panels.comments}
        onOpenChange={(value) => open("comments", value)}
        github={doc.github ?? null}
        onLocate={(comment) => {
          setLocating(comment);
          // 開いている文書のコメントは移動せず、本文の印までスクロールするだけにする
          const here =
            comment.source === source &&
            comment.path === doc.path &&
            (comment.ref ?? "") === (doc.ref ?? "");
          if (!here) nav.locate(comment);
        }}
        onChanged={() => undefined}
      />
    </div>
  );
};
