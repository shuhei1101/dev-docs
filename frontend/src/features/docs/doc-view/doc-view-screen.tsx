import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { ConversionErrorAlert } from "@/features/docs/doc-view/components/conversion-error-alert";
import { DiffBanner } from "@/features/docs/doc-view/components/diff-banner";
import { DocBody } from "@/features/docs/doc-view/components/doc-body";
import { DocBreadcrumb } from "@/features/docs/doc-view/components/doc-breadcrumb";
import { DocHeader } from "@/features/docs/doc-view/components/doc-header";
import { DocSidebar } from "@/features/docs/doc-view/components/doc-sidebar";
import { DocTabs } from "@/features/docs/doc-view/components/doc-tabs";
import { DocToc } from "@/features/docs/doc-view/components/doc-toc";
import { EmptyTab } from "@/features/docs/doc-view/components/empty-tab";
import { SidebarDrawer } from "@/features/docs/doc-view/components/sidebar-drawer";
import { findActivePage, pageTitle } from "@/features/docs/doc-view/nav";
import { baseMarkdownQueryOptions, documentQueryOptions } from "@/features/docs/doc-view/queries";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import { type TocItem, changedSections } from "@/features/docs/doc-view/toc";
import { CommentPanel } from "@/features/docs/shared/comments/comment-panel";
import { type DocComment, useCommentStore } from "@/features/docs/shared/comments/comment-store";
import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import type { NavTab } from "@/shared/api/generated/model";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import { useViewListRefs } from "@/shared/api/generated/view/view";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { Topbar } from "@/shared/components/topbar/topbar";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { usePreferencesStore } from "@/shared/stores/preferences";

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

/** 文書の画面。トップバー・種類のタブ・サイドバー・本文・目次・コメントのパネルを並べる */
export const DocViewScreen = () => {
  const params = useParams({ strict: false }) as { source: string; _splat?: string };
  const search = useSearch({ strict: false }) as DocViewSearch;
  const navigate = useNavigate();
  const { source } = params;
  const path = params._splat ?? "";

  const [searchOpen, setSearchOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [commentPanelOpen, setCommentPanelOpen] = useState(false);
  const [emptyTab, setEmptyTab] = useState<NavTab | null>(null);
  const [headings, setHeadings] = useState<TocItem[]>([]);

  const { colorScheme, singleKeyShortcuts, setColorScheme } = usePreferencesStore();
  const commentCount = useCommentStore((state) => state.comments.length);

  const query = useSuspenseQuery(documentQueryOptions(source, path, search));
  const doc = query.data;
  const refs = useViewListRefs(source).data;
  const settings = useSettingsGetSettingsSources().data;

  const active = findActivePage(doc.tabs, doc.path);
  const tabIndex = Math.max(0, doc.tabs.indexOf(active.tab));
  const baseMarkdown = useQuery(
    baseMarkdownQueryOptions(source, doc.path, doc.diff?.base ?? null),
  ).data;
  const changed =
    doc.diff && doc.markdown !== null && baseMarkdown !== undefined
      ? changedSections(doc.markdown, baseMarkdown)
      : undefined;

  // 文書が変わったら、文書の無いタブの表示を戻す
  useEffect(() => setEmptyTab(null), [doc.path]);
  useEffect(() => {
    document.title = pageTitle(active, source);
  }, [active, source]);

  useShortcut("search", () => setSearchOpen(true), { enabled: !searchOpen && !helpOpen });
  useShortcut("help", () => setHelpOpen(true), { enabled: !searchOpen && !helpOpen });

  const go = (next: { to: "/$source" | "/$source/$"; splat?: string; rev?: string; base?: string }) =>
    navigate({
      to: next.to,
      params: { source, _splat: next.splat ?? "" },
      search: { rev: next.rev, base: next.base },
    });

  const startCompare = () => {
    const current = search.rev ?? refs?.defaultRef;
    const base =
      current !== refs?.defaultRef ? refs?.defaultRef : refs?.commits?.[1]?.commit;
    if (base) void go({ to: "/$source/$", splat: doc.path, rev: search.rev, base });
  };

  const locate = (comment: DocComment) => {
    void navigate({
      to: "/$source/$",
      params: { source: comment.source, _splat: comment.path },
      search: { rev: comment.ref ?? undefined },
    });
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
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-background focus:p-2"
      >
        本文へスキップ
      </a>
      <Topbar
        screen="doc-view"
        sources={(settings?.sources ?? [])
          .filter((item) => item.status === "serving" && item.id)
          .map((item) => ({
            id: item.id as string,
            writable: item.scope.write === null || (item.scope.write?.length ?? 0) > 0,
          }))}
        currentSource={source}
        refs={refs}
        currentRef={doc.ref ?? undefined}
        commentCount={commentCount}
        colorScheme={colorScheme}
        onSourceSelect={(id) => void navigate({ to: "/$source", params: { source: id } })}
        onRefSelect={(rev) =>
          void go({ to: "/$source/$", splat: doc.path, rev, base: search.base })
        }
        onCompareStart={startCompare}
        onSearchOpen={() => setSearchOpen(true)}
        onCommentPanelToggle={() => setCommentPanelOpen((open) => !open)}
        onSidebarOpen={() => setDrawerOpen(true)}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <div className="sticky top-12 z-20 bg-background px-3">
        <DocTabs
          tabs={doc.tabs}
          currentIndex={tabIndex}
          source={source}
          search={search}
          onEmptyTab={(tab) => setEmptyTab(tab)}
        />
      </div>
      <div className="mx-auto flex max-w-screen-2xl gap-6 px-4">
        <aside className="sticky top-24 hidden h-[calc(100vh-6rem)] w-60 shrink-0 overflow-y-auto py-4 md:block">
          {sidebar()}
        </aside>
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 space-y-4 py-6" aria-busy={query.isFetching}>
          <DocBreadcrumb source={source} active={active} search={search} />
          {emptyTab ? (
            <>
              <DocHeader title={emptyTab.title} />
              <EmptyTab
                tab={emptyTab}
                index={doc.tabs.indexOf(emptyTab)}
                ref={doc.ref ?? null}
              />
            </>
          ) : (
            <>
              <DocHeader
                title={active.page?.title ?? doc.path}
                kind={active.tab.title}
                path={doc.path}
                updatedAt={doc.updatedAt}
              />
              {doc.diff && refs && (
                <DiffBanner
                  base={doc.diff.base}
                  head={doc.ref ?? refs.defaultRef}
                  refs={refs}
                  onChange={({ base, rev }) => void go({ to: "/$source/$", splat: doc.path, rev, base })}
                  onClear={() => void go({ to: "/$source/$", splat: doc.path, rev: search.rev })}
                />
              )}
              {doc.conversionError ? (
                <ConversionErrorAlert error={doc.conversionError} onRetry={() => void query.refetch()} />
              ) : (
                <DocBody
                  document={doc}
                  onHeadings={setHeadings}
                  onCommentSaved={() => setCommentPanelOpen(true)}
                />
              )}
            </>
          )}
        </main>
        <aside className="sticky top-24 hidden h-[calc(100vh-6rem)] w-56 shrink-0 overflow-y-auto py-6 xl:block">
          {!emptyTab && !doc.conversionError && <DocToc items={headings} changed={changed} />}
        </aside>
      </div>
      <SidebarDrawer open={drawerOpen} onOpenChange={setDrawerOpen}>
        {sidebar(() => setDrawerOpen(false))}
      </SidebarDrawer>
      <SearchDialog
        open={searchOpen}
        onOpenChange={setSearchOpen}
        source={source}
        ref={doc.ref ?? undefined}
        onResultSelect={(selected) =>
          void go({ to: "/$source/$", splat: selected, rev: search.rev })
        }
      />
      <ShortcutDialog
        open={helpOpen}
        onOpenChange={setHelpOpen}
        screen="doc-view"
        singleKey={singleKeyShortcuts}
      />
      <CommentPanel
        open={commentPanelOpen}
        onOpenChange={setCommentPanelOpen}
        github={doc.github ?? null}
        onLocate={locate}
        onChanged={() => undefined}
      />
    </div>
  );
};
