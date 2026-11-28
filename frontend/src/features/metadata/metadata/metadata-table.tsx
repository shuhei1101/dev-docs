import { Link } from "@tanstack/react-router";
import { Info, Plus, Trash2, Undo2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  type PendingEdit,
  usePendingEdits,
  usePendingEditsStore,
} from "@/shared/stores/pending-edits-store";
import type { MetadataColumn, MetadataKind, MetadataRow } from "@/shared/api/generated/model";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

type CellValue = string | string[];
type EditKind = PendingEdit["kind"];

const LIST_SEPARATOR = ", ";
const NEW_ID_PATTERN = /^[a-z0-9-]+$/;

/** 表の行の要素の id。レビュー中のパネルから行へ移動するときに使用する */
export const rowElementId = (kind: string, rowId: string): string =>
  `metadata-row-${kind}-${rowId}`;

const toText = (value: CellValue | undefined): string =>
  Array.isArray(value) ? value.join(LIST_SEPARATOR) : (value ?? "");

/** 入力を列の値にする（`list` の列は `, ` で区切った配列） */
const fromText = (column: MetadataColumn, text: string): CellValue =>
  column.type === "list"
    ? text
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item !== "")
    : text;

const normalize = (text: string): string => text.normalize("NFKC").toLowerCase();

/** 行の名前に使用する列（種類が持つ最初の列） */
const NAME_COLUMNS = ["name", "rule", "path"] as const;

/** 行の名前（`NAME_COLUMNS` のうち種類が持つ最初の列の値。空なら ID） */
export const rowLabel = (kind: MetadataKind, row: MetadataRow): string => {
  const key = NAME_COLUMNS.find((name) => kind.columns.some((column) => column.key === name));
  const text = toText(key === undefined ? undefined : row.values[key]);
  return text === "" ? row.id : text;
};

type EditableCellProps = {
  label: string;
  value: CellValue;
  editing: boolean;
  onStart: () => void;
  onCommit: (text: string) => void;
  onCancel: () => void;
};

/** 押した座標にある文字の位置（`element` の中の文字列の先頭からの文字数）。求められなければ `null` */
const caretOffsetAt = (element: HTMLElement, x: number, y: number): number | null => {
  const position = document.caretPositionFromPoint?.(x, y);
  const node = position?.offsetNode;
  if (!position || !node || !element.contains(node)) return null;
  const range = document.createRange();
  range.setStart(element, 0);
  range.setEnd(node, position.offset);
  return range.toString().length;
};

/** 押すと行の中で入力欄になり、押した位置に入力位置を配置する。Enter かフォーカスが移ると確定し、Esc で捨てるセル */
const EditableCell = ({ label, value, editing, onStart, onCommit, onCancel }: EditableCellProps) => {
  const text = toText(value);
  // 押した位置の文字数（キーボードで始めたときと、求められないときは末尾）
  const caret = useRef<number>(text.length);
  if (!editing) {
    return (
      <button
        type="button"
        className="w-full rounded px-1 text-left hover:bg-muted"
        aria-label={`${label} ${text === "" ? "-" : text} を編集`}
        onClick={(event) => {
          const offset =
            event.detail === 0 || text === ""
              ? null
              : caretOffsetAt(event.currentTarget, event.clientX, event.clientY);
          caret.current = Math.min(offset ?? text.length, text.length);
          onStart();
        }}
      >
        {text === "" ? <span className="text-muted-foreground">-</span> : text}
      </button>
    );
  }
  return (
    <Input
      ref={(element) => {
        if (element === null || element === document.activeElement) return;
        element.focus();
        element.setSelectionRange(caret.current, caret.current);
      }}
      aria-label={label}
      defaultValue={text}
      className="h-7 font-mono text-xs"
      onKeyDown={(event) => {
        if (event.key === "Enter") onCommit(event.currentTarget.value);
        if (event.key === "Escape") onCancel();
      }}
      onBlur={(event) => onCommit(event.currentTarget.value)}
    />
  );
};

type NewRowProps = {
  kind: MetadataKind;
  takenIds: Set<string>;
  onAdd: (id: string, values: Record<string, CellValue>) => void;
  onCancel: () => void;
};

/** 追加の行の ID の入力チェック（違反が無ければ `null`） */
const idError = (id: string, takenIds: Set<string>): string | null => {
  if (id === "") return "ID を入力してください";
  if (!NEW_ID_PATTERN.test(id)) return "ID は英小文字・数字・ハイフンで入力してください";
  if (takenIds.has(id)) return "この ID は使用されています。別の ID を入力してください";
  return null;
};

/** 「行追加」で表の末尾に出す入力用の行 */
const NewRow = ({ kind, takenIds, onAdd, onCancel }: NewRowProps) => {
  const [id, setId] = useState("");
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const idInput = useRef<HTMLInputElement>(null);
  const editable = kind.columns.filter((column) => column.editable);
  // 出したときに ID の入力欄へフォーカスを移す
  useEffect(() => idInput.current?.focus(), []);
  const errorId = `new-row-error-${kind.id}`;
  const submit = () => {
    const trimmed = id.trim();
    const found = idError(trimmed, takenIds);
    setError(found);
    if (found !== null) return;
    const values: Record<string, CellValue> = {};
    for (const column of editable) {
      const text = texts[column.key] ?? "";
      if (text.trim() !== "") values[column.key] = fromText(column, text);
    }
    onAdd(trimmed, values);
  };
  return (
    <TableRow
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel();
      }}
    >
      <TableCell colSpan={kind.columns.length + 1}>
        <div className="flex flex-wrap items-start gap-2">
          <div className="flex flex-col gap-1">
            <Input
              ref={idInput}
              aria-label="ID"
              aria-invalid={error !== null}
              aria-describedby={error === null ? undefined : errorId}
              placeholder="ID"
              className="h-7 w-40 font-mono text-xs"
              value={id}
              onChange={(event) => setId(event.target.value)}
            />
            {error !== null && (
              <p id={errorId} className="text-xs text-destructive">
                {error}
              </p>
            )}
          </div>
          {editable.map((column) => (
            <Input
              key={column.key}
              aria-label={column.label}
              placeholder={column.label}
              className="h-7 w-48 font-mono text-xs"
              value={texts[column.key] ?? ""}
              onChange={(event) =>
                setTexts((current) => ({ ...current, [column.key]: event.target.value }))
              }
            />
          ))}
          <Button size="sm" onClick={submit}>
            追加
          </Button>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            キャンセル
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
};

/** 配信していない種類の案内 */
const KindNotServed = ({ kind }: { kind: MetadataKind }) => (
  <Alert>
    <Info />
    <AlertTitle>{kind.title}を配信していません</AlertTitle>
    <AlertDescription>
      <p>
        配信元の設定（<code>project-index.yaml</code>）に次の行を追加すると、一覧に表示されます。
      </p>
      <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">{kind.hint}</pre>
    </AlertDescription>
  </Alert>
);

type CellProps = {
  source: string;
  row: MetadataRow;
  column: MetadataColumn;
  value: CellValue;
  canEdit: boolean;
  editing: boolean;
  onStart: () => void;
  onCommit: (text: string) => void;
  onCancel: () => void;
};

/** 行の値。修正できるセルはボタン、文書の列は文書の画面へのリンク、ほかは文字列 */
const Cell = ({ source, row, column, value, canEdit, ...handlers }: CellProps) => {
  if (canEdit) return <EditableCell label={column.label} value={value} {...handlers} />;
  if (column.key === "path" && row.docPath) {
    return (
      <Link
        to="/$source/$"
        params={{ source, _splat: row.docPath }}
        className="underline-offset-2 hover:underline"
      >
        {toText(value)}
      </Link>
    );
  }
  return <>{toText(value)}</>;
};

type Props = {
  source: string;
  kind: MetadataKind;
  query: string;
  /** メタデータの取得の `baseCommit`（変更の追加に指定する） */
  baseCommit: string;
};

/** 1 つの種類の表。行と列が修正できるときだけ行の中の編集・追加・削除を出す */
export const MetadataTable = ({ source, kind, query, baseCommit }: Props) => {
  const edits = usePendingEdits(source);
  const upsert = usePendingEditsStore((state) => state.upsert);
  const remove = usePendingEditsStore((state) => state.remove);
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const addButton = useRef<HTMLButtonElement>(null);
  const cancelAdding = () => {
    setAdding(false);
    addButton.current?.focus();
  };
  if (!kind.served) return <KindNotServed kind={kind} />;

  const kindId = kind.id as EditKind;
  const mine = edits.filter((edit) => edit.kind === kind.id);
  const updates = new Map(mine.filter((e) => e.op === "update").map((e) => [e.docId, e]));
  const deletes = new Map(mine.filter((e) => e.op === "delete").map((e) => [e.docId, e]));
  const words = normalize(query.trim());
  const rows = kind.rows.filter(
    (row) =>
      words === "" ||
      Object.values(row.values).some((value) => normalize(toText(value)).includes(words)),
  );
  const anyEditable = kind.id !== "config" && kind.rows.some((row) => row.editable);
  const takenIds = new Set([
    ...kind.rows.map((row) => row.id),
    ...mine.filter((e) => e.op === "add").map((e) => e.docId),
  ]);

  const commitCell = (row: MetadataRow, column: MetadataColumn, text: string) => {
    setEditing(null);
    const current = updates.get(row.id);
    upsert(source, {
      key: `${kind.id}:${row.id}:update`,
      kind: kindId,
      op: "update",
      docId: row.id,
      docKind: row.docKind ?? "",
      expectedVersion: row.version ?? null,
      docPath: row.docPath ?? null,
      values: { ...current?.values, [column.key]: fromText(column, text) },
      before: { ...current?.before, [column.key]: current?.before[column.key] ?? row.values[column.key] ?? "" },
      label: `${kind.title}: ${rowLabel(kind, row)}`,
    }, baseCommit);
  };

  const toggleDelete = (row: MetadataRow, label: string) => {
    const deleted = deletes.get(row.id);
    if (deleted !== undefined) return remove(source, deleted.key);
    upsert(source, {
      key: `${kind.id}:${row.id}:delete`,
      kind: kindId,
      op: "delete",
      docId: row.id,
      docKind: row.docKind ?? "",
      expectedVersion: row.version ?? null,
      docPath: row.docPath ?? null,
      values: {},
      before: {},
      label: `${kind.title}: ${label}`,
    }, baseCommit);
  };

  const add = (id: string, values: Record<string, CellValue>) => {
    setAdding(false);
    upsert(source, {
      key: `${kind.id}:${id}:add`,
      kind: kindId,
      op: "add",
      docId: id,
      docKind: kind.createKind ?? "",
      expectedVersion: null,
      docPath: null,
      values,
      before: {},
      label: `${kind.title}: ${toText(Object.values(values)[0]) || id}`,
    }, baseCommit);
  };

  return (
    <div className="flex min-w-0 flex-col gap-2">
      {kind.id === "config" && (
        <p className="text-xs text-muted-foreground">
          配信元の設定はこの画面では参照のみです。修正するときは project-index.yaml を編集してください。
        </p>
      )}
      {kind.id !== "config" && kind.rows.length > 0 && !anyEditable && (
        <p className="text-xs text-muted-foreground">
          この種類は直コミットを許可していないため、参照のみです。
        </p>
      )}
      {kind.rows.length === 0 && !adding ? (
        <p className="rounded-md border p-4 text-sm text-muted-foreground">
          {kind.title}はありません。{kind.canAdd && "「行追加」で追加できます。"}
        </p>
      ) : (
        <div className="w-full overflow-x-auto rounded-md border">
          <Table aria-label={`${kind.title}の表`}>
            <TableHeader>
              <TableRow>
                {kind.columns.map((column) => (
                  <TableHead key={column.key}>{column.label}</TableHead>
                ))}
                <TableHead className="w-24">
                  <span className="sr-only">操作</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const deleted = deletes.has(row.id);
                const label = rowLabel(kind, row);
                return (
                  <TableRow
                    key={row.id}
                    id={rowElementId(kind.id, row.id)}
                    tabIndex={-1}
                    className={deleted ? "line-through opacity-60" : ""}
                  >
                    {kind.columns.map((column) => {
                      const cell = `${row.id}:${column.key}`;
                      const pending = updates.get(row.id)?.values[column.key];
                      return (
                        <TableCell
                          key={column.key}
                          className={pending === undefined ? "font-mono text-xs" : "bg-primary/10 font-mono text-xs"}
                        >
                          <Cell
                            source={source}
                            row={row}
                            column={column}
                            value={(pending as CellValue | undefined) ?? row.values[column.key] ?? ""}
                            canEdit={row.editable && column.editable && !deleted}
                            editing={editing === cell}
                            onStart={() => setEditing(cell)}
                            onCommit={(text) => commitCell(row, column, text)}
                            onCancel={() => setEditing(null)}
                          />
                        </TableCell>
                      );
                    })}
                    <TableCell>
                      {kind.canDelete && row.editable && (
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={deleted ? `${label} を元に戻す` : `${label} を削除`}
                                onClick={() => toggleDelete(row, label)}
                              />
                            }
                          >
                            {deleted ? <Undo2 /> : <Trash2 />}
                          </TooltipTrigger>
                          <TooltipContent>
                            {deleted ? `${label} を元に戻す` : `${label} を削除`}
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
              {rows.length === 0 && kind.rows.length > 0 && (
                <TableRow>
                  <TableCell colSpan={kind.columns.length + 1} className="text-muted-foreground">
                    「{query}」に一致する行はありません。
                  </TableCell>
                </TableRow>
              )}
              {adding && (
                <NewRow kind={kind} takenIds={takenIds} onCancel={cancelAdding} onAdd={add} />
              )}
            </TableBody>
          </Table>
        </div>
      )}
      {kind.canAdd && (
        <Button ref={addButton} variant="outline" size="sm" className="self-start" onClick={() => setAdding(true)}>
          <Plus />
          行追加
        </Button>
      )}
    </div>
  );
};
