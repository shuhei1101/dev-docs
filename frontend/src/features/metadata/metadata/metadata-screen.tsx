import {
  type UseQueryResult,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ExternalLink, Info, Plus, Trash2, Undo2 } from "lucide-react";
import { useState } from "react";

import {
  ProjectIndexUnreachableAlert,
  toProjectIndexUnreachable,
} from "@/shared/components/project-index-unreachable";
import { SkipLink } from "@/shared/components/skip-link";
import { Topbar } from "@/shared/components/topbar/topbar";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Label } from "@/shared/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/shared/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/shared/components/ui/tabs";
import { Textarea } from "@/shared/components/ui/textarea";
import { AppError } from "@/shared/core/app-error";
import { useMediaQuery } from "@/shared/hooks/use-media-query";

/** メタデータの取得を待つ間の読み込み中の表示 */
const MetadataSkeleton = () => (
  <div
    aria-busy="true"
    aria-label="メタデータを読み込んでいます"
    className="space-y-3"
  >
    <Skeleton className="h-8 w-2/3" />
    <Skeleton className="h-48 w-full" />
  </div>
);

export type MetadataColumn = { key: string; label: string };

export type MetadataRow = {
  id: string;
  /** 行が指す文書のパス（文書の画面で開く） */
  docPath?: string;
  version: string;
  values: Record<string, string>;
};

export type MetadataKind = {
  id: string;
  title: string;
  served: boolean;
  editable: boolean;
  /** 配信していないときに案内する、配信元の設定に加える行 */
  hint?: string;
  columns: MetadataColumn[];
  rows: MetadataRow[];
};

export type MetadataResponse = {
  source: string;
  branch: string;
  kinds: MetadataKind[];
};

export type PendingEdit = {
  key: string;
  kind: string;
  rowId: string;
  /** 修正した列のキー（行の値の修正だけが持つ） */
  column?: string;
  op: "update" | "add" | "delete";
  label: string;
  before?: string;
  after?: string;
};

export type EditProblem = { key: string; message: string };

type SendResult =
  | { status: "idle" }
  | { status: "dry-run"; diffs: { key: string; diff: string }[] }
  | { status: "committed"; sha: string; branch: string }
  | { status: "rejected"; title: string; problems: EditProblem[] }
  | { status: "failed"; title: string; detail: string };

type ProblemBody = {
  title?: string;
  detail?: string;
  errors?: EditProblem[];
};

const fetchMetadata = async (source: string): Promise<MetadataResponse> => {
  const response = await fetch(`/_api/sources/${source}/metadata`);
  if (!response.ok) throw await AppError.fromResponse(response);
  return (await response.json()) as MetadataResponse;
};

const postCommits = async (args: {
  source: string;
  edits: PendingEdit[];
  message: string;
  dryRun: boolean;
}): Promise<SendResult> => {
  const response = await fetch(`/_api/sources/${args.source}/commits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      edits: args.edits,
      message: args.message,
      dryRun: args.dryRun,
    }),
  });
  const body = (await response.json()) as ProblemBody & {
    diffs?: { key: string; diff: string }[];
    commit?: { sha: string; branch: string };
  };
  if (response.ok) {
    return args.dryRun
      ? { status: "dry-run", diffs: body.diffs ?? [] }
      : {
          status: "committed",
          sha: body.commit?.sha ?? "",
          branch: body.commit?.branch ?? "",
        };
  }
  if (body.errors !== undefined) {
    return {
      status: "rejected",
      title: body.title ?? "送信できませんでした",
      problems: body.errors,
    };
  }
  return {
    status: "failed",
    title: body.title ?? "送信できませんでした",
    detail: body.detail ?? "",
  };
};

const OP_LABEL = { update: "修正", add: "追加", delete: "削除" } as const;

type KindTableProps = {
  kind: MetadataKind;
  query: string;
  edits: PendingEdit[];
  source: string;
  /** 開いたときに入力欄にしているセル（`{行の id}:{列のキー}`） */
  initialEditing?: string;
  onEdit: (edit: PendingEdit) => void;
};

const rowLabel = (kind: MetadataKind, row: MetadataRow): string =>
  row.values[kind.columns[0]?.key ?? ""] ?? row.id;

/** 表の行の要素の id。溜めた修正のパネルから行へ移るときに使う */
export const rowElementId = (kind: string, rowId: string): string =>
  `metadata-row-${kind}-${rowId}`;

type EditableCellProps = {
  label: string;
  value: string;
  editing: boolean;
  onStart: () => void;
  onCommit: (value: string) => void;
  onCancel: () => void;
};

/** 押すと行の中で入力欄になり、Enter か外へ移ると確定するセル */
const EditableCell = (props: EditableCellProps) => {
  if (!props.editing) {
    return (
      <button
        type="button"
        className="w-full rounded px-1 text-left hover:bg-muted"
        aria-label={`${props.label} を修正`}
        onClick={props.onStart}
      >
        {props.value === "" ? (
          <span className="text-muted-foreground">-</span>
        ) : (
          props.value
        )}
      </button>
    );
  }
  return (
    <Input
      ref={(element) => element?.focus()}
      aria-label={props.label}
      defaultValue={props.value}
      className="h-7 font-mono text-xs"
      onKeyDown={(event) => {
        if (event.key === "Enter") props.onCommit(event.currentTarget.value);
        if (event.key === "Escape") props.onCancel();
      }}
      onBlur={(event) => props.onCommit(event.currentTarget.value)}
    />
  );
};

type NewRowProps = {
  kind: MetadataKind;
  onAdd: (values: Record<string, string>) => void;
  onCancel: () => void;
};

/** 「行追加」で表の末尾に出す入力用の行 */
const NewRow = ({ kind, onAdd, onCancel }: NewRowProps) => {
  const [values, setValues] = useState<Record<string, string>>({});
  return (
    <TableRow>
      {kind.columns.map((column) => (
        <TableCell key={column.key}>
          <Input
            aria-label={`追加する行の${column.label}`}
            className="h-7 font-mono text-xs"
            value={values[column.key] ?? ""}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                [column.key]: event.target.value,
              }))
            }
          />
        </TableCell>
      ))}
      <TableCell className="flex items-center gap-1">
        <Button size="sm" onClick={() => onAdd(values)}>
          溜める
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          取り消す
        </Button>
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
        配信元の設定（<code>project-index.yaml</code>
        ）に、次の行を加えると一覧に出ます。
      </p>
      <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
        {kind.hint}
      </pre>
    </AlertDescription>
  </Alert>
);

/** 1 つの種類の表。直コミットを許可した種類だけ行の修正・追加・削除を出す */
const KindTable = (props: KindTableProps) => {
  const { kind, query, edits, source, onEdit } = props;
  const [editing, setEditing] = useState<string | null>(
    props.initialEditing ?? null,
  );
  const [adding, setAdding] = useState(false);
  if (!kind.served) return <KindNotServed kind={kind} />;
  const words = query.trim().toLowerCase();
  const rows = kind.rows.filter(
    (row) =>
      words === "" ||
      Object.values(row.values).some((value) =>
        value.toLowerCase().includes(words),
      ),
  );
  const pending = new Map(
    edits
      .filter((edit) => edit.kind === kind.id)
      .map((edit) => [`${edit.rowId}:${edit.column ?? ""}`, edit]),
  );
  const deleted = new Set(
    edits
      .filter((edit) => edit.kind === kind.id && edit.op === "delete")
      .map((edit) => edit.rowId),
  );
  const commitCell = (
    row: MetadataRow,
    column: MetadataColumn,
    value: string,
  ) => {
    setEditing(null);
    const before = row.values[column.key] ?? "";
    if (value === before) return;
    onEdit({
      key: `${kind.id}:${row.id}:${column.key}:update`,
      kind: kind.id,
      rowId: row.id,
      column: column.key,
      op: "update",
      label: `${kind.title}: ${rowLabel(kind, row)} の${column.label}`,
      before,
      after: value,
    });
  };
  return (
    <div className="flex min-w-0 flex-col gap-2">
      {!kind.editable && (
        <p className="text-xs text-muted-foreground">
          この種類は直コミットを許可していないため、参照だけです。
        </p>
      )}
      {kind.rows.length === 0 && !adding ? (
        <p className="rounded-md border p-4 text-sm text-muted-foreground">
          {kind.title}はまだありません。
          {kind.editable && "「行追加」で追加できます。"}
        </p>
      ) : (
        <div className="w-full overflow-x-auto rounded-md border">
          <Table>
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
              {rows.map((row) => (
                <TableRow
                  key={row.id}
                  id={rowElementId(kind.id, row.id)}
                  className={
                    deleted.has(row.id) ? "line-through opacity-60" : ""
                  }
                >
                  {kind.columns.map((column) => {
                    const cell = `${row.id}:${column.key}`;
                    const value =
                      pending.get(cell)?.after ?? row.values[column.key] ?? "";
                    return (
                      <TableCell
                        key={column.key}
                        className={
                          pending.has(cell)
                            ? "bg-primary/10 font-mono text-xs"
                            : "font-mono text-xs"
                        }
                      >
                        {kind.editable && !deleted.has(row.id) ? (
                          <EditableCell
                            label={`${rowLabel(kind, row)} の${column.label}`}
                            value={value}
                            editing={editing === cell}
                            onStart={() => setEditing(cell)}
                            onCommit={(next) => commitCell(row, column, next)}
                            onCancel={() => setEditing(null)}
                          />
                        ) : (
                          value
                        )}
                      </TableCell>
                    );
                  })}
                  <TableCell className="flex items-center gap-1">
                    {row.docPath !== undefined && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${rowLabel(kind, row)} の文書を開く`}
                        render={
                          <Link
                            to="/$source/$"
                            params={{ source, _splat: row.docPath }}
                          />
                        }
                        nativeButton={false}
                      >
                        <ExternalLink />
                      </Button>
                    )}
                    {kind.editable && !deleted.has(row.id) && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${rowLabel(kind, row)} を削除`}
                        onClick={() =>
                          onEdit({
                            key: `${kind.id}:${row.id}:delete`,
                            kind: kind.id,
                            rowId: row.id,
                            op: "delete",
                            label: `${kind.title}: ${rowLabel(kind, row)}`,
                          })
                        }
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {adding && (
                <NewRow
                  kind={kind}
                  onCancel={() => setAdding(false)}
                  onAdd={(values) => {
                    setAdding(false);
                    const rowId = `new-${Date.now()}`;
                    onEdit({
                      key: `${kind.id}:${rowId}:add`,
                      kind: kind.id,
                      rowId,
                      op: "add",
                      label: `${kind.title}: ${values[kind.columns[0]?.key ?? ""] ?? ""}`,
                    });
                  }}
                />
              )}
            </TableBody>
          </Table>
        </div>
      )}
      {kind.editable && !adding && (
        <Button
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => setAdding(true)}
        >
          <Plus />
          行追加
        </Button>
      )}
    </div>
  );
};

type PendingPanelProps = {
  open: boolean;
  source: string;
  branch: string;
  edits: PendingEdit[];
  result: SendResult;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onDiscard: (key: string) => void;
  onLocate: (edit: PendingEdit) => void;
  onDryRun: () => void;
  onSendStart: () => void;
};

/** 溜めた修正の一覧と、試しに書いた差分・送信の結果 */
const PendingPanel = (props: PendingPanelProps) => {
  const { edits, result } = props;
  const narrow = useMediaQuery("(max-width: 47.99rem)");
  const problems =
    result.status === "rejected"
      ? new Map(result.problems.map((p) => [p.key, p.message]))
      : new Map<string, string>();
  const diffs =
    result.status === "dry-run"
      ? new Map(result.diffs.map((d) => [d.key, d.diff]))
      : new Map<string, string>();
  return (
    <Sheet
      modal={false}
      disablePointerDismissal
      open={props.open}
      onOpenChange={props.onOpenChange}
    >
      <SheetContent
        side={narrow ? "bottom" : "right"}
        overlay={false}
        className={
          narrow
            ? "max-h-2/3 w-full overflow-y-auto"
            : "top-12! bottom-0! h-auto! w-96 max-w-full overflow-y-auto"
        }
      >
        <SheetHeader>
          <SheetTitle>溜めた修正</SheetTitle>
          <SheetDescription>
            {props.source} の {props.branch} へ、{edits.length}{" "}
            件をまとめてコミットします。
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-4">
          {result.status === "committed" && (
            <Alert>
              <AlertTitle>コミットしてプッシュしました</AlertTitle>
              <AlertDescription>
                <span className="font-mono">{result.sha}</span>（{result.branch}
                ）
              </AlertDescription>
            </Alert>
          )}
          {result.status === "rejected" && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>{result.title}</AlertTitle>
              <AlertDescription>
                コミットしていません。修正ごとの理由を確認してください。
              </AlertDescription>
            </Alert>
          )}
          {result.status === "failed" && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>{result.title}</AlertTitle>
              <AlertDescription>
                <p>{result.detail}</p>
                <p>溜めた修正は残っています。</p>
              </AlertDescription>
            </Alert>
          )}
          {edits.length === 0 && result.status !== "committed" && (
            <p className="text-sm text-muted-foreground">
              溜めた修正はありません。
            </p>
          )}
          <ul className="flex flex-col gap-2">
            {edits.map((edit) => (
              <li key={edit.key} className="rounded-md border p-2">
                <div className="flex items-start gap-2">
                  <Badge variant="outline">{OP_LABEL[edit.op]}</Badge>
                  <button
                    type="button"
                    className="flex-1 text-left text-sm underline-offset-2 hover:underline"
                    aria-label={`${edit.label} の行へ移る`}
                    onClick={() => props.onLocate(edit)}
                  >
                    {edit.label}
                  </button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`${edit.label} の修正を取り消す`}
                    onClick={() => props.onDiscard(edit.key)}
                  >
                    <Undo2 />
                  </Button>
                </div>
                {edit.before !== undefined && edit.after !== undefined && (
                  <p className="mt-1 font-mono text-xs">
                    {edit.before} → {edit.after}
                  </p>
                )}
                {diffs.has(edit.key) && (
                  <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
                    {diffs.get(edit.key)}
                  </pre>
                )}
                {problems.has(edit.key) && (
                  <p className="mt-1 text-xs text-destructive">
                    {problems.get(edit.key)}
                  </p>
                )}
              </li>
            ))}
          </ul>
          {edits.length > 0 && (
            <div className="flex gap-2 pb-4">
              <Button
                variant="outline"
                disabled={props.busy}
                onClick={props.onDryRun}
              >
                試しに書く
              </Button>
              <Button disabled={props.busy} onClick={props.onSendStart}>
                {result.status === "failed" ? "もう一度送信" : "まとめて送信"}
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
};

type SendDialogProps = {
  open: boolean;
  source: string;
  branch: string;
  count: number;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onSend: (message: string) => void;
};

/** 既定のブランチへプッシュする前の確認 */
const SendDialog = (props: SendDialogProps) => {
  const [message, setMessage] = useState("");
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>まとめて送信しますか？</DialogTitle>
          <DialogDescription>
            {props.source} の {props.branch} へ {props.count} 件の修正を 1
            つのコミットにしてプッシュします。プッシュした後は取り消せません。
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="commit-message">コミットの説明</Label>
          <Textarea
            id="commit-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => props.onOpenChange(false)}>
            取り消す
          </Button>
          <Button
            disabled={props.busy || message.trim() === ""}
            onClick={() => props.onSend(message)}
          >
            送信する
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

type MetadataBodyProps = {
  metadata: UseQueryResult<MetadataResponse>;
  tab: string | null;
  query: string;
  edits: PendingEdit[];
  source: string;
  initialEditing?: string;
  onTabChange: (tab: string) => void;
  onEdit: (edit: PendingEdit) => void;
};

/** 読み込み中・取得できない・種類ごとのタブと表 */
const MetadataBody = ({
  metadata,
  tab,
  query,
  edits,
  source,
  initialEditing,
  onTabChange,
  onEdit,
}: MetadataBodyProps) => {
  const unreachable = toProjectIndexUnreachable(metadata.error);
  return (
    <>
      {metadata.isPending && <MetadataSkeleton />}
      {metadata.isError && (
        <ProjectIndexUnreachableAlert
          kind={unreachable?.kind ?? "failed"}
          address={unreachable?.address ?? ""}
          reason={unreachable?.reason ?? String(metadata.error)}
          onReload={() => window.location.reload()}
        />
      )}
      {metadata.data !== undefined && (
        <Tabs
          value={tab ?? metadata.data.kinds[0]?.id}
          onValueChange={(value) => onTabChange(String(value))}
          className="min-w-0 flex-col"
        >
          <TabsList className="h-auto w-full flex-wrap justify-start">
            {metadata.data.kinds.map((kind) => (
              <TabsTrigger
                key={kind.id}
                value={kind.id}
                className="h-7 flex-none"
              >
                {kind.title}
                <span className="ml-1 text-xs text-muted-foreground">
                  {kind.served ? kind.rows.length : "-"}
                </span>
              </TabsTrigger>
            ))}
          </TabsList>
          {metadata.data.kinds.map((kind) => (
            <TabsContent key={kind.id} value={kind.id} className="min-w-0">
              <KindTable
                kind={kind}
                initialEditing={
                  initialEditing?.startsWith(`${kind.id}:`)
                    ? initialEditing.slice(kind.id.length + 1)
                    : undefined
                }
                query={query}
                edits={edits}
                source={source}
                onEdit={onEdit}
              />
            </TabsContent>
          ))}
        </Tabs>
      )}
    </>
  );
};

type Props = {
  source: string;
  /** 開いたときに溜めてある修正（画面を開き直しても残る修正） */
  initialEdits?: PendingEdit[];
  initialPanelOpen?: boolean;
  initialConfirmOpen?: boolean;
  /** 開いたときに入力欄にしているセル（`{種類}:{行の id}:{列のキー}`） */
  initialEditing?: string;
};

/** 1 つの配信元のメタデータを、種類ごとの表で参照・修正する画面 */
export const MetadataScreen = ({
  source,
  initialEdits = [],
  initialPanelOpen = false,
  initialConfirmOpen = false,
  initialEditing,
}: Props) => {
  const metadata = useQuery({
    queryKey: ["metadata", source],
    queryFn: () => fetchMetadata(source),
  });
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<string | null>(
    initialEditing?.split(":")[0] ?? null,
  );
  const [edits, setEdits] = useState<PendingEdit[]>(initialEdits);
  const [panelOpen, setPanelOpen] = useState(initialPanelOpen);
  const [confirmOpen, setConfirmOpen] = useState(initialConfirmOpen);
  const [result, setResult] = useState<SendResult>({ status: "idle" });
  const send = useMutation({
    mutationFn: postCommits,
    onSuccess: (next) => {
      setResult(next);
      setConfirmOpen(false);
      if (next.status === "committed") setEdits([]);
    },
  });
  const branch = metadata.data?.branch ?? "";
  const locate = (edit: PendingEdit) => {
    setTab(edit.kind);
    setQuery("");
    requestAnimationFrame(() =>
      document
        .getElementById(rowElementId(edit.kind, edit.rowId))
        ?.scrollIntoView({ block: "center" }),
    );
  };
  const addEdit = (edit: PendingEdit) =>
    setEdits((current) => [
      ...current.filter((item) => item.key !== edit.key),
      edit,
    ]);
  return (
    <div className="min-h-screen bg-background">
      <SkipLink />
      <Topbar
        screen="metadata"
        currentSource={source}
        sources={[{ id: source, writable: true }]}
        pendingEditCount={edits.length}
        colorScheme="system"
        onColorSchemeToggle={() => undefined}
        onPendingPanelToggle={() => setPanelOpen((open) => !open)}
      />
      <main
        id="main"
        className="mx-auto flex max-w-6xl min-w-0 flex-col gap-4 p-4"
      >
        <h1 className="text-2xl font-semibold">{source} のメタデータ</h1>
        <div className="flex max-w-sm flex-col gap-1.5">
          <Label htmlFor="metadata-filter">表を絞り込む</Label>
          <Input
            id="metadata-filter"
            type="search"
            placeholder="用語・パス・タグ"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <MetadataBody
          metadata={metadata}
          tab={tab}
          query={query}
          edits={edits}
          source={source}
          initialEditing={initialEditing}
          onTabChange={setTab}
          onEdit={addEdit}
        />
      </main>
      <PendingPanel
        open={panelOpen}
        source={source}
        branch={branch}
        edits={edits}
        result={result}
        busy={send.isPending}
        onOpenChange={setPanelOpen}
        onLocate={locate}
        onDiscard={(key) =>
          setEdits((current) => current.filter((edit) => edit.key !== key))
        }
        onDryRun={() =>
          send.mutate({ source, edits, message: "", dryRun: true })
        }
        onSendStart={() => setConfirmOpen(true)}
      />
      <SendDialog
        open={confirmOpen}
        source={source}
        branch={branch}
        count={edits.length}
        busy={send.isPending}
        onOpenChange={setConfirmOpen}
        onSend={(message) =>
          send.mutate({ source, edits, message, dryRun: false })
        }
      />
    </div>
  );
};
