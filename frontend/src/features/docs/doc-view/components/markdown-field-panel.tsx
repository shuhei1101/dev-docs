import { type RefObject, useDeferredValue, useRef } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import { bodyEditKey, upsertBodyEdit, usePendingBodyValue } from "@/features/docs/doc-view/edit";
import type { DocumentEdit, EditBlock } from "@/shared/api/generated/model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/shared/components/ui/sheet";
import { Textarea } from "@/shared/components/ui/textarea";
import { useMediaQuery } from "@/shared/hooks/use-media-query";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";

const NARROW_QUERY = "(max-width: 47.99rem)";

type FormProps = {
  source: string;
  docId: string;
  edit: DocumentEdit;
  block: EditBlock;
  editorRef: RefObject<HTMLTextAreaElement | null>;
};

/** Markdown の文字列の項目の、エディタとプレビュー。書き換えはその場で編集中の変更に入れる */
const MarkdownFieldForm = ({ source, docId, edit, block, editorRef }: FormProps) => {
  const before = typeof block.value === "string" ? block.value : "";
  const pending = usePendingBodyValue(source, edit, block.path);
  const draft = typeof pending === "string" ? pending : before;
  const deferred = useDeferredValue(draft);
  const set = (value: string) =>
    upsertBodyEdit(source, edit, { path: block.path, label: block.label, before, value });
  const revert = () => usePendingEditsStore.getState().remove(source, bodyEditKey(edit, block.path));
  return (
    <div className="flex flex-col gap-3 px-4 pb-4">
      <div className="flex flex-col gap-1.5">
        <div className="flex min-h-6 items-center gap-2">
          <Label htmlFor="markdown-field">本文</Label>
          {pending !== undefined && (
            <>
              <Badge variant="outline">変更あり</Badge>
              <Button variant="ghost" size="sm" className="ml-auto" onClick={revert}>
                元に戻す
              </Button>
            </>
          )}
        </div>
        <Textarea
          ref={editorRef}
          id="markdown-field"
          value={draft}
          rows={12}
          className="font-mono text-base md:text-sm"
          onChange={(event) => set(event.target.value)}
        />
      </div>
      <section aria-label="プレビュー" className="rounded-md border p-3">
        <MarkdownPreview markdown={deferred} docId={`${docId}#${block.path}`} />
      </section>
    </div>
  );
};

type Props = {
  source: string;
  /** mdmark の `docId`（`{source}@{ref}:{path}`） */
  docId: string;
  edit: DocumentEdit;
  /** 編集する項目（null は閉じている） */
  block: EditBlock | null;
  onClose: () => void;
};

/** 表示した場所で Markdown の文字列の項目を編集する、画面の横のパネル */
export const MarkdownFieldPanel = ({ source, docId, edit, block, onClose }: Props) => {
  const narrow = useMediaQuery(NARROW_QUERY);
  // パネルを開いたらエディタへフォーカスを移す
  const editorRef = useRef<HTMLTextAreaElement>(null);
  return (
    <Sheet modal={false} disablePointerDismissal open={block !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side={narrow ? "bottom" : "right"}
        overlay={false}
        initialFocus={editorRef}
        className={
          narrow ? "max-h-2/3 w-full overflow-y-auto" : "top-12! bottom-0! h-auto! w-lg max-w-full overflow-y-auto"
        }
      >
        <SheetHeader>
          <SheetTitle className="wrap-anywhere">{block?.label ?? ""} の編集</SheetTitle>
          <SheetDescription>
            <code className="font-mono wrap-anywhere">{block?.path ?? ""}</code>
          </SheetDescription>
        </SheetHeader>
        {block !== null && (
          <MarkdownFieldForm
            key={block.path}
            source={source}
            docId={docId}
            edit={edit}
            block={block}
            editorRef={editorRef}
          />
        )}
      </SheetContent>
    </Sheet>
  );
};
