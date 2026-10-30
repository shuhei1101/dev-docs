import { useEffect, useRef } from "react";
import { Controller } from "react-hook-form";

import { useSourceForm } from "@/features/settings/settings/hooks/use-source-form";
import { fieldOf } from "@/features/settings/settings/problem-errors";
import type { SourceFormValues } from "@/features/settings/settings/form";
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
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: SettingsSourceRow[];
  index: number | null;
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

/** 末尾の句点と直し方（最初の句点より後ろ）を除いた違反の文言 */
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

/** 配信元の追加・編集のダイアログ */
export const SourceEditDialog = ({
  open,
  onOpenChange,
  sources,
  index,
}: Props) => {
  const { form, errors, submit, summary, saving } = useSourceForm({
    sources,
    index,
    onSaved: () => onOpenChange(false),
  });
  const editing = index !== null;
  const idRef = useRef<HTMLInputElement | null>(null);
  const configRef = useRef<HTMLTextAreaElement | null>(null);
  const idField = form.register("id");
  const configField = form.register("config");
  const invalidCount = Object.keys(errors).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
              {editing
                ? `配信元 ${sources[index].id ?? ""}`
                : "端末の設定に配信元を追加します。"}
            </DialogDescription>
          </DialogHeader>
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
              hint="画面の URL と文書の MCP の source に使います。英小文字・数字・ハイフンで入力します。"
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
              placeholder="~/repo/sample-docs/dev-docs.yaml"
              aria-invalid={errors.config !== undefined}
              {...configField}
              ref={(element) => {
                configField.ref(element);
                configRef.current = element;
              }}
            />
          </Field>
          <div className="space-y-1.5">
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
              外すと、設定を残したまま配信を止めます。
            </p>
          </div>
          <Field
            id="source-read"
            label="読み取りの範囲"
            required
            hint="glob を 1 行に 1 つ。当たる作業場所から、この配信元の文書を読めます。"
            error={errors.read?.message}
          >
            <Textarea
              id="source-read"
              placeholder="~/repo/**"
              aria-invalid={errors.read !== undefined}
              {...form.register("read")}
            />
          </Field>
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
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              キャンセル
            </Button>
            <Button type="submit" disabled={saving}>
              {editing ? "保存" : "追加"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
