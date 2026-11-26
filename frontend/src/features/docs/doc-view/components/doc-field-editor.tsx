import { Check, Pencil } from "lucide-react";
import { useState } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import { upsertBodyEdit, usePendingBodyValue } from "@/features/docs/doc-view/edit";
import type { DocumentEdit, EditBlock } from "@/shared/api/generated/model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";
import type { EditValue } from "@/shared/stores/pending-edits-store";

type Rows = Array<Record<string, string>>;

type BlockProps = {
  source: string;
  edit: DocumentEdit;
  block: EditBlock;
};

const isRows = (value: EditValue): value is Rows => Array.isArray(value) && value.every((item) => typeof item === "object");

const textOf = (value: EditValue): string => (typeof value === "string" ? value : "");

/** 書き換えをその場で編集中の変更に入れる（元の値に戻すと変更から除く） */
const useBlockValue = ({ source, edit, block }: BlockProps) => {
  const pending = usePendingBodyValue(source, edit, block.path);
  const set = (value: EditValue) =>
    upsertBodyEdit(source, edit, { path: block.path, label: block.label, before: block.value, value });
  return { current: pending ?? block.value, changed: pending !== undefined, set };
};

/** 表の行を Markdown の表にする（編集中の行をブロックの描画に反映する） */
const rowsMarkdown = (columns: string[], rows: Rows): string =>
  [
    `| ${columns.join(" | ")} |`,
    `| ${columns.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${columns.map((column) => row[column] ?? "").join(" | ")} |`),
  ].join("\n");

/** 元の値が描いた Markdown に現れる回数 */
const occurrences = (markdown: string, value: string): number =>
  value === "" ? 0 : markdown.split(value).length - 1;

/** 編集中の値を描いたブロックの Markdown */
const blockMarkdown = (block: EditBlock, current: EditValue, changed: boolean): string => {
  if (!changed) return block.markdown;
  if (block.type === "table") return rowsMarkdown(block.columns ?? [], isRows(current) ? current : []);
  const before = textOf(block.value);
  // 元の値がちょうど 1 回現れる: その箇所だけを編集中の値に置き換える
  if (occurrences(block.markdown, before) === 1) return block.markdown.replace(before, () => textOf(current));
  // 現れない（リンクの書き換え・表のセルの変換）か 2 回以上現れる: 編集中の値をそのまま描く
  return textOf(current);
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

type BlockViewProps = BlockProps & {
  docId: string;
  editing: boolean;
  onEditingChange: (editing: boolean) => void;
  onMarkdownOpen: (block: EditBlock) => void;
};

/** 描いた本文の 1 ブロックと、その横の編集のボタン。押すとブロックを編集の部品に置き換える */
const EditableBlock = ({ source, docId, edit, block, editing, onEditingChange, onMarkdownOpen }: BlockViewProps) => {
  const value = useBlockValue({ source, edit, block });
  const setEditing = onEditingChange;
  const inline = editing && block.type !== "markdown";
  return (
    <div data-edit-path={block.path} className="doc-edit-block rounded-md p-2 hover:bg-muted/40 focus-within:bg-muted/40">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1 wrap-anywhere">
          {inline && block.type === "table" && (
            <RowsTable block={block} rows={isRows(value.current) ? value.current : []} onChange={value.set} />
          )}
          {inline && block.type !== "table" && (
            <ValueInput block={block} value={textOf(value.current)} onChange={value.set} onDone={() => setEditing(false)} />
          )}
          {!inline && (
            <MarkdownPreview markdown={blockMarkdown(block, value.current, value.changed)} docId={`${docId}#${block.path}`} />
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
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
  source: string;
  /** mdmark の `docId`（`{source}@{ref}:{path}`） */
  docId: string;
  edit: DocumentEdit;
  onMarkdownOpen: (block: EditBlock) => void;
};

/** YAML の文書の描いた本文を、表示した場所で修正できる項目のブロックごとに編集のボタンを付けて並べる */
export const DocFieldEditor = ({ source, docId, edit, onMarkdownOpen }: Props) => {
  // 部品を出している項目のパス（`string`・`enum`・`table` の項目）
  const [editing, setEditing] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      {edit.blocks.map((block) => (
        <EditableBlock
          key={block.path}
          source={source}
          docId={docId}
          edit={edit}
          block={block}
          editing={editing === block.path}
          onEditingChange={(next) => setEditing(next ? block.path : null)}
          onMarkdownOpen={onMarkdownOpen}
        />
      ))}
    </div>
  );
};

type TitleProps = { source: string; edit: DocumentEdit; block: EditBlock };

/** 表示した場所で修正するときの文書のタイトル。横の編集のボタンで、タイトルをその場の入力欄にする */
export const EditableTitle = ({ source, edit, block }: TitleProps) => {
  const value = useBlockValue({ source, edit, block });
  const [editing, setEditing] = useState(false);
  return (
    <div data-edit-path={block.path} className="flex min-w-0 flex-1 items-center gap-2">
      {editing ? (
        <ValueInput block={block} value={textOf(value.current)} onChange={value.set} onDone={() => setEditing(false)} />
      ) : (
        <h1 className="min-w-0 text-doc-title font-doc-title wrap-anywhere">{textOf(value.current)}</h1>
      )}
      {value.changed && <Badge variant="outline">変更あり</Badge>}
      {editing ? (
        <Button variant="ghost" size="icon-sm" aria-label={`${block.label} の編集を終了`} onClick={() => setEditing(false)}>
          <Check />
        </Button>
      ) : (
        <Button variant="ghost" size="icon-sm" aria-label={`${block.label} を編集`} onClick={() => setEditing(true)}>
          <Pencil />
        </Button>
      )}
    </div>
  );
};
