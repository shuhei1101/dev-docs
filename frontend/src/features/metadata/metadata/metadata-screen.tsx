import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ExternalLink, Info, Plus, Trash2, Undo2 } from "lucide-react";
import { useState } from "react";

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
  if (!response.ok) throw new Error(`metadata: ${response.status}`);
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
  onEdit: (edit: PendingEdit) => void;
};

/** 1 つの種類の表。直コミットを許可した種類だけ行の修正・追加・削除を出す */
const KindTable = ({ kind, query, edits, source, onEdit }: KindTableProps) => {
  if (!kind.served) {
    return (
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
  }
  const words = query.trim().toLowerCase();
  const rows = kind.rows.filter(
    (row) =>
      words === "" ||
      Object.values(row.values).some((value) =>
        value.toLowerCase().includes(words),
      ),
  );
  const deleted = new Set(
    edits
      .filter((edit) => edit.kind === kind.id && edit.op === "delete")
      .map((edit) => edit.rowId),
  );
  return (
    <div className="flex flex-col gap-2">
      {!kind.editable && (
        <p className="text-xs text-muted-foreground">
          この種類は直コミットを許可していないため、参照だけです。
        </p>
      )}
      <div className="overflow-x-auto rounded-md border">
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
                className={deleted.has(row.id) ? "line-through opacity-60" : ""}
              >
                {kind.columns.map((column) => (
                  <TableCell key={column.key} className="font-mono text-xs">
                    {row.values[column.key]}
                  </TableCell>
                ))}
                <TableCell className="flex items-center gap-1">
                  {row.docPath !== undefined && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`${row.values[kind.columns[0]?.key ?? ""] ?? row.id} の文書を開く`}
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
                      aria-label={`${row.values[kind.columns[0]?.key ?? ""] ?? row.id} を削除`}
                      onClick={() =>
                        onEdit({
                          key: `${kind.id}:${row.id}:delete`,
                          kind: kind.id,
                          rowId: row.id,
                          op: "delete",
                          label: `${kind.title}: ${row.values[kind.columns[0]?.key ?? ""] ?? row.id}`,
                        })
                      }
                    >
                      <Trash2 />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {kind.editable && (
        <Button variant="outline" size="sm" className="self-start">
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
  onDryRun: () => void;
  onSendStart: () => void;
};

/** 溜めた修正の一覧と、試しに書いた差分・送信の結果 */
const PendingPanel = (props: PendingPanelProps) => {
  const { edits, result } = props;
  const problems =
    result.status === "rejected"
      ? new Map(result.problems.map((p) => [p.key, p.message]))
      : new Map<string, string>();
  const diffs =
    result.status === "dry-run"
      ? new Map(result.diffs.map((d) => [d.key, d.diff]))
      : new Map<string, string>();
  return (
    <Sheet open={props.open} onOpenChange={props.onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
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
                  <span className="flex-1 text-sm">{edit.label}</span>
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

type Props = {
  source: string;
  /** 開いたときに溜めてある修正（画面を開き直しても残る修正） */
  initialEdits?: PendingEdit[];
  initialPanelOpen?: boolean;
  initialConfirmOpen?: boolean;
};

/** 1 つの配信元のメタデータを、種類ごとの表で参照・修正する画面 */
export const MetadataScreen = ({
  source,
  initialEdits = [],
  initialPanelOpen = false,
  initialConfirmOpen = false,
}: Props) => {
  const metadata = useQuery({
    queryKey: ["metadata", source],
    queryFn: () => fetchMetadata(source),
  });
  const [query, setQuery] = useState("");
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
      <main id="main" className="mx-auto flex max-w-6xl flex-col gap-4 p-4">
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
        {metadata.data !== undefined && (
          <Tabs defaultValue={metadata.data.kinds[0]?.id}>
            <TabsList className="flex-wrap">
              {metadata.data.kinds.map((kind) => (
                <TabsTrigger key={kind.id} value={kind.id}>
                  {kind.title}
                  <span className="ml-1 text-xs text-muted-foreground">
                    {kind.served ? kind.rows.length : "-"}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
            {metadata.data.kinds.map((kind) => (
              <TabsContent key={kind.id} value={kind.id}>
                <KindTable
                  kind={kind}
                  query={query}
                  edits={edits}
                  source={source}
                  onEdit={addEdit}
                />
              </TabsContent>
            ))}
          </Tabs>
        )}
      </main>
      <PendingPanel
        open={panelOpen}
        source={source}
        branch={branch}
        edits={edits}
        result={result}
        busy={send.isPending}
        onOpenChange={setPanelOpen}
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
