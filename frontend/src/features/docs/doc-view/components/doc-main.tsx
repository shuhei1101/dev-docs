import { ConversionErrorAlert } from "@/features/docs/doc-view/components/conversion-error-alert";
import { DiffBanner } from "@/features/docs/doc-view/components/diff-banner";
import { DocBody } from "@/features/docs/doc-view/components/doc-body";
import { DocBreadcrumb } from "@/features/docs/doc-view/components/doc-breadcrumb";
import { DocHeader } from "@/features/docs/doc-view/components/doc-header";
import { EmptyTab } from "@/features/docs/doc-view/components/empty-tab";
import type { ActivePage } from "@/features/docs/doc-view/nav";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import type { TocItem } from "@/features/docs/doc-view/toc";
import type { DocComment } from "@/features/docs/shared/comments/comment-store";
import type {
  DocumentResponse,
  NavTab,
  RefsResponse,
} from "@/shared/api/generated/model";

type Props = {
  doc: DocumentResponse;
  active: ActivePage;
  search: DocViewSearch;
  refs: RefsResponse | undefined;
  emptyTab: NavTab | null;
  busy: boolean;
  onHeadings: (items: TocItem[]) => void;
  onCommentSaved: () => void;
  locating: DocComment | null;
  onLocated: () => void;
  onRetry: () => void;
  onCompare: (rev: string | undefined, base: string) => void;
  onClearDiff: () => void;
};

type ContentProps = Omit<Props, "emptyTab" | "busy" | "search">;

const DocContent = ({ doc, active, refs, ...handlers }: ContentProps) => (
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
        onChange={({ base, rev }) => handlers.onCompare(rev, base)}
        onClear={handlers.onClearDiff}
      />
    )}
    {doc.conversionError ? (
      <ConversionErrorAlert
        error={doc.conversionError}
        onRetry={handlers.onRetry}
      />
    ) : (
      <DocBody
        document={doc}
        onHeadings={handlers.onHeadings}
        onCommentSaved={handlers.onCommentSaved}
        locating={handlers.locating}
        onLocated={handlers.onLocated}
      />
    )}
  </>
);

/** 文書の画面の本文の領域（パンくず・文書のヘッダー・差分の案内・本文か変換の失敗か文書の無いタブ） */
export const DocMain = ({ emptyTab, busy, ...content }: Props) => (
  <main
    id="main"
    tabIndex={-1}
    className="min-w-0 flex-1 space-y-4 py-6"
    aria-busy={busy}
  >
    <DocBreadcrumb
      source={content.doc.source}
      active={content.active}
      search={content.search}
    />
    {emptyTab ? (
      <>
        <DocHeader title={emptyTab.title} />
        <EmptyTab
          tab={emptyTab}
          index={content.doc.tabs.indexOf(emptyTab)}
          ref={content.doc.ref ?? null}
        />
      </>
    ) : (
      <DocContent {...content} />
    )}
  </main>
);
