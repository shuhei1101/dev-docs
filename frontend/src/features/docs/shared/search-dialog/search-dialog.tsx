import { useQueries } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import { useEffect, useRef, useState } from "react";

import { splitHighlight } from "@/features/docs/shared/search-dialog/highlight";
import { AppError } from "@/shared/core/app-error";
import { getViewSearchPageQueryOptions } from "@/shared/api/generated/view/view";
import type { ScreenSearchItem } from "@/shared/api/generated/model";
import {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
} from "@/shared/components/ui/command";
import { Badge } from "@/shared/components/ui/badge";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import { cn } from "@/shared/lib/utils";

const DEBOUNCE_MS = 200;

/** 結果の 1 件目が選ばれるのを待つ最大のフレーム数 */
const SELECTION_WAIT_FRAMES = 30;

/** 画面の検索の `limit` の上限 */
const SEARCH_LIMIT = 100;

type Scope = "current" | "all";
type Order = "matches" | "name";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: string;
  ref?: string;
  /** 全ての配信元の検索で問い合わせる配信中の配信元の ID */
  sources?: string[];
  onResultSelect: (path: string, source: string) => void;
};

/** 一致した行の数（`matchCount`）を持つ結果。応答に無ければ一致した箇所の数を使用する */
type SearchItem = ScreenSearchItem & { matchCount?: number };

type Row = SearchItem & { source: string; matches: number };

type Failure = { source: string; reason: string };

const reasonOf = (error: unknown) =>
  error instanceof AppError
    ? (error.problem?.detail ?? error.message)
    : String(error);

type StatusProps = {
  sent: string;
  pending: boolean;
  error: string | undefined;
  total: number | undefined;
  shown: number;
  excludedCount: number | undefined;
  revision: string | undefined;
};

/** 件数・読み込み中・失敗・一致なしの文言（変わるたびに支援技術へ通知する） */
const SearchStatus = ({
  sent,
  pending,
  error,
  total,
  shown,
  excludedCount,
  revision,
}: StatusProps) => {
  let text = "";
  if (sent !== "") {
    if (error) text = error;
    else if (pending && total === undefined) text = "検索しています";
    else if (total === 0 && excludedCount)
      text = `該当する文書はありません。配信元の設定で検索から除外した文書を含めると ${excludedCount} 件あります。`;
    else if (total === 0)
      text = "該当する文書はありません。別の条件を試してください。";
    else if (total !== undefined) {
      text = `${total} 件${revision ? `（リビジョン ${revision}）` : ""}`;
      if (shown < total) text += `。一致した行の数の多い ${shown} 件を表示`;
      if (excludedCount) text += `・検索から除外 ${excludedCount} 件`;
    }
  }
  return (
    <p
      role="status"
      className="px-3 py-2 text-xs text-muted-foreground empty:hidden"
    >
      {text}
    </p>
  );
};

type SegmentProps<T extends string> = {
  name: string;
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
};

/** 横に並べた択一のラジオ（Tab で入り、矢印キーで選ぶ） */
const Segment = <T extends string>({
  name,
  label,
  value,
  options,
  onChange,
}: SegmentProps<T>) => (
  <fieldset className="flex min-w-0 items-center gap-2">
    <legend className="sr-only">{label}</legend>
    <span aria-hidden="true" className="shrink-0 text-xs text-muted-foreground">
      {label}
    </span>
    <div className="flex shrink-0 rounded-md border border-input p-0.5">
      {options.map((option) => (
        <label
          key={option.value}
          className={cn(
            "cursor-pointer rounded px-2 py-0.5 text-xs whitespace-nowrap has-focus-visible:ring-2 has-focus-visible:ring-ring",
            option.value === value
              ? "bg-primary text-primary-foreground"
              : "text-foreground hover:bg-accent",
          )}
        >
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={option.value === value}
            onChange={() => onChange(option.value)}
            className="sr-only"
          />
          {option.label}
        </label>
      ))}
    </div>
  </fieldset>
);

/** 配信元の文書を単語で検索するダイアログ（開いている配信元か、全ての配信元） */
export const SearchDialog = ({
  open,
  onOpenChange,
  source,
  ref: revision,
  sources = [],
  onResultSelect,
}: Props) => {
  const [query, setQuery] = useState("");
  const [sent, setSent] = useState("");
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [scope, setScope] = useState<Scope>("current");
  const [order, setOrder] = useState<Order>("matches");

  // 入力の 200 ミリ秒の待ちの後に問い合わせる
  useEffect(() => {
    const timer = setTimeout(() => setSent(query.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const targets =
    scope === "all" ? Array.from(new Set([source, ...sources])) : [source];
  /* eslint-disable react-hooks/refs -- `ref` は React の ref でなくリビジョンを指す props */
  const searches = useQueries({
    queries: targets.map((id) => ({
      ...getViewSearchPageQueryOptions(id, {
        q: sent,
        // 全ての配信元の検索は、各配信元の default_ref を検索する
        ref: scope === "all" ? undefined : revision,
        limit: SEARCH_LIMIT,
        include_excluded: includeExcluded || undefined,
      }),
      enabled: open && sent !== "",
    })),
  });
  /* eslint-enable react-hooks/refs */

  const settled = searches.filter((search) => search.data !== undefined);
  const failures: Failure[] = searches.flatMap((search, index) =>
    search.error
      ? [{ source: targets[index] ?? "", reason: reasonOf(search.error) }]
      : [],
  );
  const rows: Row[] =
    sent === ""
      ? []
      : searches.flatMap((search, index) =>
          (search.data?.items ?? []).map((item: SearchItem) => ({
            ...item,
            source: targets[index] ?? source,
            matches: item.matchCount ?? item.snippets.length,
          })),
        );
  rows.sort((a, b) =>
    order === "name"
      ? a.name.localeCompare(b.name, "ja")
      : b.matches - a.matches || a.name.localeCompare(b.name, "ja"),
  );
  const total =
    sent === "" || settled.length === 0
      ? undefined
      : settled.reduce(
          (sum, search) => sum + (search.data?.totalCount ?? 0),
          0,
        );
  const excludedCount = includeExcluded
    ? undefined
    : settled.reduce(
        (sum, search) => sum + (search.data?.excludedCount ?? 0),
        0,
      );
  // 開いている配信元の検索の失敗は件数の場所の文言にし、全ての配信元の検索の失敗は配信元ごとに並べる
  const error =
    scope === "current" && failures[0] ? failures[0].reason : undefined;

  // cmdk は最初に選んだ結果を `aria-activedescendant` に反映しないため、結果が出たら選んでいる結果を指す
  const inputRef = useRef<HTMLInputElement>(null);
  const resultKey = rows.map((row) => `${row.source}:${row.path}`).join("\n");
  useEffect(() => {
    let frame = 0;
    let attempts = 0;
    const point = () => {
      const selected = document.querySelector(
        '[cmdk-item][aria-selected="true"]',
      );
      if (selected?.id) {
        inputRef.current?.setAttribute("aria-activedescendant", selected.id);
      } else if (attempts < SELECTION_WAIT_FRAMES) {
        attempts += 1;
        frame = requestAnimationFrame(point);
      }
    };
    frame = requestAnimationFrame(point);
    return () => cancelAnimationFrame(frame);
  }, [resultKey]);

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="文書を検索"
      description="単語を入力して文書を探します"
      className="top-12 flex max-h-5/6 w-full max-w-3xl flex-col sm:max-w-3xl max-md:inset-0 max-md:top-0 max-md:h-full max-md:max-h-none max-md:max-w-none max-md:translate-x-0 max-md:rounded-none!"
    >
      <Command shouldFilter={false} className="min-h-0 flex-1">
        <CommandInput
          ref={inputRef}
          value={query}
          onValueChange={setQuery}
          placeholder="文書を検索"
        />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-3 py-2">
          <Segment
            name="search-scope"
            label="検索の範囲"
            value={scope}
            options={[
              { value: "current", label: `この配信元（${source}）` },
              { value: "all", label: "全ての配信元" },
            ]}
            onChange={setScope}
          />
          <Segment
            name="search-order"
            label="並び順"
            value={order}
            options={[
              { value: "matches", label: "一致した行の数" },
              { value: "name", label: "名前" },
            ]}
            onChange={setOrder}
          />
          <div className="flex items-center gap-2">
            <Switch
              id="search-include-excluded"
              size="sm"
              checked={includeExcluded}
              onCheckedChange={setIncludeExcluded}
            />
            <Label
              htmlFor="search-include-excluded"
              className="text-xs font-normal text-muted-foreground"
            >
              配信元の設定で検索から除外した文書も含める
            </Label>
          </div>
        </div>
        <SearchStatus
          sent={sent}
          pending={searches.some((search) => search.isFetching)}
          error={error}
          total={total}
          shown={rows.length}
          excludedCount={excludedCount}
          revision={scope === "all" ? undefined : revision}
        />
        {scope === "all" && sent !== "" && failures.length > 0 && (
          <ul
            aria-label="検索できなかった配信元"
            className="mx-3 mb-2 space-y-1 rounded-md border border-destructive px-3 py-2 text-xs"
          >
            {failures.map((failure) => (
              <li key={failure.source} className="wrap-anywhere">
                <span className="font-mono">{failure.source}</span>
                を検索できませんでした。{failure.reason}
              </li>
            ))}
          </ul>
        )}
        <CommandList className="max-h-none min-h-0 flex-1">
          {rows.length > 0 && (
            <div role="group" className="divide-y divide-border">
              {rows.map((row) => (
                <CommandPrimitive.Item
                  key={`${row.source}:${row.path}`}
                  value={`${row.source}:${row.path}`}
                  onSelect={() => {
                    onResultSelect(row.path, row.source);
                    onOpenChange(false);
                  }}
                  className="flex min-w-0 cursor-default flex-col gap-0.5 px-3 py-2 text-sm outline-hidden select-none aria-selected:bg-muted"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="min-w-0 truncate font-medium">
                      {row.name}
                    </span>
                    {row.excluded && (
                      <Badge variant="outline" className="shrink-0">
                        検索から除外
                      </Badge>
                    )}
                    <span className="ml-auto shrink-0 text-xs whitespace-nowrap text-muted-foreground tabular-nums">
                      一致 {row.matches} 行
                    </span>
                  </span>
                  <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                    {scope === "all" && (
                      <Badge variant="secondary" className="shrink-0 font-mono">
                        {row.source}
                      </Badge>
                    )}
                    <code className="min-w-0 truncate font-mono">
                      {row.path}
                    </code>
                  </span>
                  {row.snippets.slice(0, 1).map((snippet) => (
                    <span
                      key={snippet}
                      className="min-w-0 text-xs wrap-anywhere text-muted-foreground"
                    >
                      {splitHighlight(snippet, sent).map((part, index) =>
                        part.match ? (
                          <mark
                            key={index}
                            className="bg-warning/30 text-foreground"
                          >
                            {part.text}
                          </mark>
                        ) : (
                          <span key={index}>{part.text}</span>
                        ),
                      )}
                    </span>
                  ))}
                </CommandPrimitive.Item>
              ))}
            </div>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  );
};
