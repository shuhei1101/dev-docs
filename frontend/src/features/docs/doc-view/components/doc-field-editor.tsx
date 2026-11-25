import { Check, Pencil } from "lucide-react";
import { useState } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import { type DocEdit, type EditBlock, upsertBodyEdit, usePendingBodyValue } from "@/features/docs/doc-view/edit";
import type { DocumentResponse } from "@/shared/api/generated/model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";

type Rows = Array<Record<string, string>>;

type BlockProps = {
  doc: DocumentResponse;
  edit: DocEdit;
  block: EditBlock;
};

const textOf = (value: EditBlock["value"]): string => (typeof value === "string" ? value : JSON.stringify(value));

/** 書き換えをその場で編集中の変更に入れる（元の値に戻すと変更から除く） */
const useBlockValue = ({ doc, edit, block }: BlockProps) => {
  const before = textOf(block.value);
  const pending = usePendingBodyValue(doc, block.path);
  const set = (value: string) => upsertBodyEdit({ doc, edit, path: block.path, label: block.label, before, value });
  return { before, current: pending ?? before, changed: pending !== undefined, set };
};

/** 表の行を Markdown の表にする（編集中の値をブロックの描画に反映する） */
const rowsMarkdown = (heading: string, columns: string[], rows: Rows): string =>
  [
    heading,
    "",
    `| ${columns.join(" | ")} |`,
    `| ${columns.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${columns.map((column) => row[column] ?? "").join(" | ")} |`),
    "",
  ].join("\n");

/** 編集中の値を描いたブロックの Markdown（元の値の箇所を置き換える） */
const blockMarkdown = (block: EditBlock, current: string): string => {
  if (block.type !== "table") return block.markdown.replace(textOf(block.value), current);
  const heading = block.markdown.split("\n")[0] ?? "";
  return rowsMarkdown(heading, block.columns ?? [], JSON.parse(current) as Rows);
};

/** 短い文字列・enum の入力欄。フォーカスが離れると確定する */
const ValueInput = ({ block, value, onChange, onDone }: { block: EditBlock; value: string; onChange: (value: string) => void; onDone: () => void }) =>
  block.type === "enum" ? (
    <Select
      items={(block.options ?? []).map((option) => ({ value: option, label: option }))}
      value={value}
      onValueChange={(next) => next !== null && onChange(String(next))}
    >
      <SelectTrigger aria-label={block.label} className="w-full md:w-60">
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
      aria-label={block.label}
      value={value}
      className="min-w-0 flex-1"
      // 編集を始めたブロックの入力欄へフォーカスを移す
      // eslint-disable-next-line jsx-a11y/no-autofocus
      autoFocus
      onChange={(event) => onChange(event.target.value)}
      onBlur={onDone}
      onKeyDown={(event) => {
        if ((event.key === "Enter" || event.key === "Escape") && !event.nativeEvent.isComposing) onDone();
      }}
    />
  );

/** 平らなオブジェクトの配列の項目の、セルを直接修正できる表 */
const RowsTable = ({ block, rows, onChange }: { block: EditBlock; rows: Rows; onChange: (rows: Rows) => void }) => {
  const columns = block.columns ?? Object.keys(rows[0] ?? {});
  return (
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
                    value={row[column] ?? ""}
                    onChange={(event) =>
                      onChange(rows.map((item, position) => (position === index ? { ...item, [column]: event.target.value } : item)))
                    }
                  />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

type BlockViewProps = BlockProps & { onMarkdownOpen: (block: EditBlock) => void };

/** 描いた本文の 1 ブロックと、その横の編集のボタン。押すとブロックを編集の部品に置き換える */
const EditableBlock = ({ doc, edit, block, onMarkdownOpen }: BlockViewProps) => {
  const value = useBlockValue({ doc, edit, block });
  const [editing, setEditing] = useState(false);
  const inline = editing && block.type !== "markdown";
  return (
    <div data-edit-path={block.path} className="group relative rounded-md p-1 hover:bg-muted/40 focus-within:bg-muted/40">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1 wrap-anywhere">
          {inline && block.type === "table" && (
            <RowsTable block={block} rows={JSON.parse(value.current) as Rows} onChange={(rows) => value.set(JSON.stringify(rows))} />
          )}
          {inline && block.type !== "table" && (
            <ValueInput block={block} value={value.current} onChange={value.set} onDone={() => setEditing(false)} />
          )}
          {!inline && <MarkdownPreview markdown={blockMarkdown(block, value.current)} docId={`${doc.path}#${block.path}`} />}
        </div>
        <div className="flex shrink-0 items-center gap-1 pt-1">
          {value.changed && <Badge variant="outline">変更あり</Badge>}
          {inline ? (
            <Button variant="ghost" size="icon-sm" aria-label={`${block.label} の編集を終了`} onClick={() => setEditing(false)}>
              <Check />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`${block.label} を編集`}
              onClick={() => (block.type === "markdown" ? onMarkdownOpen(block) : setEditing(true))}
            >
              <Pencil />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

type Props = {
  doc: DocumentResponse;
  edit: DocEdit;
  onMarkdownOpen: (block: EditBlock) => void;
};

/** YAML の文書の描いた本文を、変換が目印を付けたブロックごとに編集のボタンを付けて並べる */
export const DocFieldEditor = ({ doc, edit, onMarkdownOpen }: Props) => (
  <div className="space-y-2">
    {edit.blocks.map((block) => (
      <EditableBlock key={block.path} doc={doc} edit={edit} block={block} onMarkdownOpen={onMarkdownOpen} />
    ))}
  </div>
);
