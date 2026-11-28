import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { type Control, Controller } from "react-hook-form";

import type { ConfirmRequest } from "@/shared/components/confirm-dialog";

import { useSourceForm } from "@/features/settings/settings/hooks/use-source-form";
import { fieldOf } from "@/features/settings/settings/problem-errors";
import {
  type SourceFormValues,
  type StorageChoice,
  type StorageType,
  storedStorage,
} from "@/features/settings/settings/form";
import type { SettingsSourceRow } from "@/shared/api/generated/model";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";
import { useLeaveGuard } from "@/shared/hooks/use-leave-guard";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: SettingsSourceRow[];
  index: number | null;
  /** 端末の設定の取得の `version`（`useSourceForm` へ渡す） */
  version?: string | null;
};

type FieldProps = {
  id: string;
  label: string;
  required: boolean;
  hint?: string;
  error?: string;
  children: React.ReactNode;
};

const Field = ({ id, label, required, hint, error, children }: FieldProps) => (
  <div className="space-y-1.5">
    <Label htmlFor={id}>
      {label}
      <span className="text-xs font-normal text-muted-foreground">
        {required ? "必須" : "任意"}
      </span>
    </Label>
    {children}
    {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    {error && (
      <p id={`${id}-error`} className="text-xs text-destructive">
        {error}
      </p>
    )}
  </div>
);

type FailureSummaryProps = {
  summary: { path: string; message: string }[];
  invalidCount: number;
  /** 違反の行を押したときに、その入力欄へフォーカスを移す */
  onFocusField: (name: keyof SourceFormValues) => void;
  rowIndex: number;
};

/** 末尾の句点と修正方法（最初の句点より後ろ）を除いた違反の文言 */
const headline = (message: string): string => message.replace(/。.*$/s, "");

/** 保存の失敗のまとめ（入力チェックに引っかかったときと、保存の 422 のとき） */
const FailureSummary = ({
  summary,
  invalidCount,
  onFocusField,
  rowIndex,
}: FailureSummaryProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const visible = summary.length > 0 || invalidCount > 0;
  // まとめが出たときにフォーカスを移す
  useEffect(() => {
    if (visible) ref.current?.focus();
  }, [visible]);
  if (!visible) return null;
  return (
    <Alert variant="destructive" role="alert" tabIndex={-1} ref={ref}>
      <AlertTitle>
        保存できませんでした（{summary.length || invalidCount} 件）
      </AlertTitle>
      {summary.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-4">
            {summary.map((item) => {
              const name = fieldOf(item.path, rowIndex);
              return (
                <li key={`${item.path}:${item.message}`}>
                  {name ? (
                    <button
                      type="button"
                      className="text-left underline underline-offset-2"
                      onClick={() => onFocusField(name)}
                    >
                      {headline(item.message)}
                    </button>
                  ) : (
                    headline(item.message)
                  )}{" "}
                  <code className="font-mono text-xs">{item.path}</code>
                </li>
              );
            })}
          </ul>
        </AlertDescription>
      )}
    </Alert>
  );
};

const STORAGE_OPTIONS: { value: StorageChoice; label: string }[] = [
  { value: "auto", label: "自動" },
  { value: "git", label: "Git" },
  { value: "disk", label: "ディスク" },
];

type StorageFieldProps = {
  control: Control<SourceFormValues>;
  /** 開いた行の保存済みの読み書きの方法（追加・保存済みの値が無い行は null） */
  stored: StorageType | null;
};

/** 読み書きの方法のセレクト。保存済みの値を持つ行は自動を選べない */
const StorageField = ({ control, stored }: StorageFieldProps) => {
  const options = STORAGE_OPTIONS.filter(
    (option) => stored === null || option.value !== "auto",
  );
  return (
    <Field
      id="source-storage"
      label="読み書きの方法"
      required={false}
      hint={
        stored === null
          ? "自動は、フォルダが Git の作業ツリーの中なら Git、外ならディスクで読み書きします。コミットしないフォルダはディスクを選択します。"
          : "Git はコミットから読み、ディスクはフォルダのファイルをそのまま読みます。保存済みの読み書きの方法は自動に戻せません。"
      }
    >
      <Controller
        control={control}
        name="storage"
        render={({ field }) => (
          <Select
            items={options}
            value={field.value ?? "auto"}
            onValueChange={(next) => next !== null && field.onChange(next)}
          >
            <SelectTrigger id="source-storage" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </Field>
  );
};

type FooterProps = {
  editing: boolean;
  saving: boolean;
  disabled: boolean;
  onCancel: () => void;
};

/** キャンセルと、保存を待つ間は回る表示を出す追加・保存のボタン */
const EditDialogFooter = ({ editing, saving, disabled, onCancel }: FooterProps) => (
  <DialogFooter>
    <Button type="button" variant="outline" onClick={onCancel}>
      キャンセル
    </Button>
    <Button type="submit" disabled={disabled}>
      {saving && <Loader2 aria-hidden="true" className="animate-spin" />}
      {editing ? "保存" : "追加"}
    </Button>
  </DialogFooter>
);

/** 入力したまま画面の中で移る前に出す確認のダイアログの文面 */
const LEAVE_CONFIRM: ConfirmRequest = {
  title: "入力した内容を破棄して移動しますか?",
  description: "配信元のダイアログに入力した内容は保存されていません。",
  confirmLabel: "破棄して移動",
  destructive: true,
};

/** 配信元の追加・編集のダイアログ */
export const SourceEditDialog = ({
  open,
  onOpenChange,
  sources,
  index,
  version,
}: Props) => {
  const { form, errors, submit, summary, conflict, gone, saving } =
    useSourceForm({
      sources,
      index,
      onSaved: () => onOpenChange(false),
      version,
    });
  const editing = index !== null;
  // 入力はどこにも残らないので、タブを閉じる・再読み込みに加えて画面の中の移動も止める
  useLeaveGuard(open && form.formState.isDirty, { navigation: LEAVE_CONFIRM });
  // 一覧を取得し直しても見出しの配信元が変わらないよう、開いたときの名前を持つ
  const [name] = useState(() =>
    index === null ? "" : (sources[index].id ?? ""),
  );
  const idRef = useRef<HTMLInputElement | null>(null);
  const configRef = useRef<HTMLTextAreaElement | null>(null);
  const idField = form.register("id");
  const configField = form.register("config");
  const invalidCount = Object.keys(errors).length;
  // 保存済みの読み書きの方法は、project-index が今の値で埋め直すため自動に戻せない
  const [stored] = useState(() =>
    index === null ? null : storedStorage(sources[index]),
  );

  return (
    // 外側のクリックで入力を失わないよう、Esc とキャンセルでだけ閉じる
    <Dialog open={open} onOpenChange={onOpenChange} disablePointerDismissal>
      <DialogContent
        initialFocus={editing ? configRef : idRef}
        className="max-h-screen overflow-y-auto sm:max-w-lg"
      >
        <form onSubmit={submit} noValidate className="space-y-4">
          <DialogHeader>
            <DialogTitle>
              {editing ? "配信元を編集" : "配信元を追加"}
            </DialogTitle>
            <DialogDescription>
              {editing ? `配信元 ${name}` : "端末の設定に配信元を追加します。"}
            </DialogDescription>
          </DialogHeader>
          {gone && (
            <Alert role="alert">
              <AlertTitle>
                配信元が削除されたため保存できませんでした
              </AlertTitle>
              <AlertDescription>
                この画面を開いた後に、他のプロセスがこの配信元を端末の設定から削除しました。一覧を確認してください。
              </AlertDescription>
            </Alert>
          )}
          {conflict && !gone && (
            <Alert role="alert">
              <AlertTitle>他の変更があったため保存できませんでした</AlertTitle>
              <AlertDescription>
                この画面を開いた後に、他のプロセスが端末の設定を変更しました。一覧を最新の内容にしました。入力した内容を確認し、もう一度保存してください。
              </AlertDescription>
            </Alert>
          )}
          <FailureSummary
            summary={summary}
            invalidCount={invalidCount}
            rowIndex={index ?? sources.length}
            onFocusField={(name) => form.setFocus(name)}
          />
          {!editing && (
            <Field
              id="source-id"
              label="配信元の ID"
              required
              hint="画面の URL と文書の MCP の source に使用します。英小文字・数字・ハイフンで入力します。"
              error={errors.id?.message}
            >
              <Input
                id="source-id"
                autoComplete="off"
                aria-invalid={errors.id !== undefined}
                {...idField}
                ref={(element) => {
                  idField.ref(element);
                  idRef.current = element;
                }}
              />
            </Field>
          )}
          <Field
            id="source-config"
            label="設定ファイル"
            required
            hint="1 行に 1 つ。後のファイルが前のファイルの同じキーを上書きします。"
            error={errors.config?.message}
          >
            <Textarea
              id="source-config"
              placeholder="~/repo/sample-docs/project-index.yaml"
              aria-invalid={errors.config !== undefined}
              {...configField}
              ref={(element) => {
                configField.ref(element);
                configRef.current = element;
              }}
            />
          </Field>
          <div
            role="group"
            aria-labelledby="source-enabled-heading"
            className="space-y-1.5"
          >
            <p id="source-enabled-heading" className="text-sm font-medium">
              配信
            </p>
            <div className="flex items-center justify-between">
              <Label htmlFor="source-enabled">配信する</Label>
              <Controller
                control={form.control}
                name="enabled"
                render={({ field }) => (
                  <Switch
                    id="source-enabled"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              オフにすると、設定を残したまま配信を止めます。
            </p>
          </div>
          <Field
            id="source-read"
            label="読み取りの範囲"
            required
            hint="glob を 1 行に 1 つ。当たる作業場所から、この配信元の文書を参照できます。"
            error={errors.read?.message}
          >
            <Textarea
              id="source-read"
              placeholder="~/repo/**"
              aria-invalid={errors.read !== undefined}
              {...form.register("read")}
            />
          </Field>
          <div
            role="group"
            aria-labelledby="source-outside-read-heading"
            className="space-y-1.5"
          >
            <p id="source-outside-read-heading" className="text-sm font-medium">
              範囲の外からの参照
            </p>
            <div className="flex items-center justify-between">
              <Label htmlFor="source-outside-read">
                範囲の外から参照できるようにする
              </Label>
              <Controller
                control={form.control}
                name="outsideRead"
                render={({ field }) => (
                  <Switch
                    id="source-outside-read"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              オフにすると、読み取りの範囲に当たらない作業場所からは参照できません。
            </p>
          </div>
          <StorageField control={form.control} stored={stored} />
          <Field
            id="source-write"
            label="書き込みの範囲"
            required={false}
            hint="glob を 1 行に 1 つ。当たる作業場所から、この配信元の文書へ書き込めます。"
            error={errors.write?.message}
          >
            <Textarea
              id="source-write"
              aria-invalid={errors.write !== undefined}
              {...form.register("write")}
            />
          </Field>
          <EditDialogFooter
            editing={editing}
            saving={saving}
            disabled={saving || gone}
            onCancel={() => onOpenChange(false)}
          />
        </form>
      </DialogContent>
    </Dialog>
  );
};
