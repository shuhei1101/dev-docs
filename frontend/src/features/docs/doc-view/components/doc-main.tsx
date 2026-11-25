import { ConversionErrorAlert } from "@/features/docs/doc-view/components/conversion-error-alert";
import { DiffBanner } from "@/features/docs/doc-view/components/diff-banner";
import { DocBody } from "@/features/docs/doc-view/components/doc-body";
import { DocBreadcrumb } from "@/features/docs/doc-view/components/doc-breadcrumb";
import { DocEditBar } from "@/features/docs/doc-view/components/doc-edit-bar";
import { DocFieldEditor, EditableTitle } from "@/features/docs/doc-view/components/doc-field-editor";
import { DocHeader } from "@/features/docs/doc-view/components/doc-header";
import { EmptyTab } from "@/features/docs/doc-view/components/empty-tab";
import { WholeFileEditor } from "@/features/docs/doc-view/components/whole-file-editor";
import { type EditBlock, docEditOf } from "@/features/docs/doc-view/edit";
import type { ActivePage } from "@/features/docs/doc-view/nav";
import type { DocEditMode, DocViewSearch } from "@/features/docs/doc-view/search";
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
  onCommentSaved: () => void;
  locating: DocComment | null;
  onLocated: () => void;
  /** 比較元の本文と表のキー（`DocBody` へそのまま指定する） */
  baseMarkdown?: { markdown: string; tableKeys: string[] } | null;
  onRetry: () => void;
  onCompare: (rev: string | undefined, base: string) => void;
  onClearDiff: () => void;
  onEditModeChange: (mode: DocEditMode | undefined) => void;
  onMarkdownFieldOpen: (block: EditBlock) => void;
};

type ContentProps = Omit<Props, "emptyTab" | "busy"> & { editMode: DocEditMode | undefined };

/** 本文か、編集の表示（表示した場所で修正・ファイル全体の編集） */
const DocBodyOrEditor = ({ doc, editMode, ...handlers }: ContentProps) => {
  const edit = docEditOf(doc);
  if (edit?.editable && editMode === "file") return <WholeFileEditor key={doc.path} doc={doc} edit={edit} />;
  if (edit?.editable && editMode === "fields" && edit.language === "yaml") {
    return <DocFieldEditor doc={doc} edit={edit} onMarkdownOpen={handlers.onMarkdownFieldOpen} />;
  }
  return (
    <DocBody
      document={doc}
      onCommentSaved={handlers.onCommentSaved}
      locating={handlers.locating}
      onLocated={handlers.onLocated}
      baseMarkdown={handlers.baseMarkdown}
    />
  );
};

/** 表示した場所で修正するときだけ、タイトルを編集のボタンを持つタイトルにする */
const titleNodeOf = (doc: ContentProps["doc"], editMode: DocEditMode | undefined) => {
  const edit = docEditOf(doc);
  if (!edit?.editable || editMode !== "fields" || edit.titleBlock === undefined) return undefined;
  return <EditableTitle doc={doc} edit={edit} block={edit.titleBlock} />;
};

const DocContent = ({ doc, active, refs, ...handlers }: ContentProps) => (
  <>
    <DocHeader
      titleNode={titleNodeOf(doc, handlers.editMode)}
      title={active.page?.title ?? doc.path}
      kind={active.tab.title}
      path={doc.path}
      updatedAt={doc.updatedAt}
      actions={
        doc.diff ? null : (
          <DocEditBar edit={docEditOf(doc)} mode={handlers.editMode} onModeChange={handlers.onEditModeChange} />
        )
      }
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
      <DocBodyOrEditor doc={doc} active={active} refs={refs} {...handlers} />
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
      emptyTab={emptyTab}
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
      <DocContent {...content} editMode={content.search.edit} />
    )}
  </main>
);
