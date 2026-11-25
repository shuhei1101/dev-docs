import { useDeferredValue } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import { type DocEdit, type EditBlock, upsertBodyEdit, usePendingBodyValue } from "@/features/docs/doc-view/edit";
import type { DocumentResponse } from "@/shared/api/generated/model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/shared/components/ui/sheet";
import { Textarea } from "@/shared/components/ui/textarea";
import { useMediaQuery } from "@/shared/hooks/use-media-query";

const NARROW_QUERY = "(max-width: 47.99rem)";

type FormProps = {
  doc: DocumentResponse;
  edit: DocEdit;
  block: EditBlock;
};

/** Markdown の文字列の項目の、エディタとプレビュー。書き換えはその場で編集中の変更に入れる */
const MarkdownFieldForm = ({ doc, edit, block }: FormProps) => {
  const before = typeof block.value === "string" ? block.value : "";
  const pending = usePendingBodyValue(doc, block.path);
  const draft = pending ?? before;
  const deferred = useDeferredValue(draft);
  const set = (value: string) => upsertBodyEdit({ doc, edit, path: block.path, label: block.label, before, value });
  return (
    <div className="flex flex-col gap-3 px-4 pb-4">
      <div className="flex flex-col gap-1.5">
        <div className="flex min-h-6 items-center gap-2">
          <Label htmlFor="markdown-field">本文</Label>
          {pending !== undefined && (
            <>
              <Badge variant="outline">変更あり</Badge>
              <Button variant="ghost" size="sm" className="ml-auto" onClick={() => set(before)}>
                元に戻す
              </Button>
            </>
          )}
        </div>
        <Textarea
          id="markdown-field"
          value={draft}
          rows={12}
          className="font-mono text-base md:text-sm"
          onChange={(event) => set(event.target.value)}
        />
      </div>
      <section aria-label="プレビュー" className="rounded-md border p-3">
        <MarkdownPreview markdown={deferred} docId={`${doc.path}#${block.path}`} />
      </section>
    </div>
  );
};

type Props = {
  doc: DocumentResponse;
  edit: DocEdit;
  /** 編集する項目（null は閉じている） */
  block: EditBlock | null;
  onClose: () => void;
};

/** 表示した場所で Markdown の文字列の項目を編集する、画面の横のパネル */
export const MarkdownFieldPanel = ({ doc, edit, block, onClose }: Props) => {
  const narrow = useMediaQuery(NARROW_QUERY);
  return (
    <Sheet modal={false} disablePointerDismissal open={block !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side={narrow ? "bottom" : "right"}
        overlay={false}
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
        {block !== null && <MarkdownFieldForm key={block.path} doc={doc} edit={edit} block={block} />}
      </SheetContent>
    </Sheet>
  );
};
