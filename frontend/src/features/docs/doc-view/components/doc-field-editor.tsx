import { Pencil } from "lucide-react";
import { useState } from "react";

import { type DocEdit, type EditBlock, upsertBodyEdit, usePendingBodyValue } from "@/features/docs/doc-view/edit";
import type { DocumentResponse } from "@/shared/api/generated/model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";

type BlockProps = {
  doc: DocumentResponse;
  edit: DocEdit;
  block: EditBlock;
};

const textOf = (value: EditBlock["value"]): string => (typeof value === "string" ? value : JSON.stringify(value));

/** 編集中の変更があることのマーカー */
const ChangedBadge = () => <Badge variant="outline">変更あり</Badge>;

/** 短い文字列・enum の値 1 つを、その場で修正する */
const ValueBlock = ({ doc, edit, block }: BlockProps) => {
  const before = textOf(block.value);
  const pending = usePendingBodyValue(doc, block.path);
  const current = pending ?? before;
  const [draft, setDraft] = useState<string | null>(null);
  const id = `edit-${block.path}`;
  const apply = () => {
    if (draft === null) return;
    upsertBodyEdit({ doc, edit, path: block.path, label: block.label, before, value: draft });
    setDraft(null);
  };
  if (draft === null) {
    return (
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 wrap-anywhere">{current}</p>
        {pending !== undefined && <ChangedBadge />}
        <Button variant="ghost" size="icon-sm" aria-label={`${block.label} を編集`} onClick={() => setDraft(current)}>
          <Pencil />
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-center">
      {block.type === "enum" ? (
        <Select
          items={(block.options ?? []).map((option) => ({ value: option, label: option }))}
          value={draft}
          onValueChange={(next) => next !== null && setDraft(String(next))}
        >
          <SelectTrigger id={id} aria-label={block.label} className="w-full md:w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(block.options ?? []).map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <Input
          id={id}
          aria-label={block.label}
          value={draft}
          className="min-w-0 flex-1"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.nativeEvent.isComposing) apply();
            if (event.key === "Escape") setDraft(null);
          }}
        />
      )}
      <div className="flex shrink-0 gap-2">
        <Button size="sm" onClick={apply}>
          適用
        </Button>
        <Button variant="outline" size="sm" onClick={() => setDraft(null)}>
          キャンセル
        </Button>
      </div>
    </div>
  );
};

type MarkdownBlockProps = BlockProps & { onOpen: (block: EditBlock) => void };

/** Markdown の文字列の項目。編集は画面の横のパネルで行う */
const MarkdownBlock = ({ doc, block, onOpen }: MarkdownBlockProps) => {
  const pending = usePendingBodyValue(doc, block.path);
  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1 rounded-md bg-muted/50 p-3 text-sm whitespace-pre-wrap wrap-anywhere">
        {pending ?? textOf(block.value)}
      </div>
      {pending !== undefined && <ChangedBadge />}
      <Button variant="ghost" size="icon-sm" aria-label={`${block.label} を編集`} onClick={() => onOpen(block)}>
        <Pencil />
      </Button>
    </div>
  );
};

type Rows = Array<Record<string, string>>;

/** 平らなオブジェクトの配列の項目を、セルを直接修正できる表にする */
const TableBlock = ({ doc, edit, block }: BlockProps) => {
  const original = Array.isArray(block.value) ? block.value : [];
  const pending = usePendingBodyValue(doc, block.path);
  const rows: Rows = pending === undefined ? original : (JSON.parse(pending) as Rows);
  const columns = block.columns ?? Object.keys(original[0] ?? {});
  const change = (index: number, column: string, value: string) => {
    const next = rows.map((row, position) => (position === index ? { ...row, [column]: value } : row));
    upsertBodyEdit({
      doc,
      edit,
      path: block.path,
      label: block.label,
      before: JSON.stringify(original),
      value: JSON.stringify(next),
    });
  };
  return (
    <div className="space-y-1">
      {pending !== undefined && <ChangedBadge />}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column}>{column}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => (
              // 行は位置で指す（並べ替えは表の操作に持たない）
              <TableRow key={index}>
                {columns.map((column) => (
                  <TableCell key={column} className="p-1">
                    <Input
                      aria-label={`${block.label} の ${index + 1} 行目の ${column}`}
                      defaultValue={row[column] ?? ""}
                      onBlur={(event) => {
                        if (event.target.value !== (row[column] ?? "")) change(index, column, event.target.value);
                      }}
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

type Props = {
  doc: DocumentResponse;
  edit: DocEdit;
  onMarkdownOpen: (block: EditBlock) => void;
};

/** YAML の文書の本文を、項目ごとにスキーマの型から選んだ部品で修正する */
export const DocFieldEditor = ({ doc, edit, onMarkdownOpen }: Props) => (
  <div className="space-y-6">
    {edit.blocks.map((block) => (
      <section key={block.path} aria-labelledby={`edit-heading-${block.path}`} className="space-y-2">
        <h2 id={`edit-heading-${block.path}`} className="text-lg font-semibold">
          {block.label}
          <code className="ml-2 font-mono text-xs font-normal text-muted-foreground">{block.path}</code>
        </h2>
        {block.type === "markdown" && <MarkdownBlock doc={doc} edit={edit} block={block} onOpen={onMarkdownOpen} />}
        {block.type === "table" && <TableBlock doc={doc} edit={edit} block={block} />}
        {(block.type === "string" || block.type === "enum") && <ValueBlock doc={doc} edit={edit} block={block} />}
      </section>
    ))}
  </div>
);
