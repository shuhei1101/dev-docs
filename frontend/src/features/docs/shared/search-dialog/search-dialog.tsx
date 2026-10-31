import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { splitHighlight } from "@/features/docs/shared/search-dialog/highlight";
import { AppError } from "@/shared/core/app-error";
import { getViewSearchPageQueryOptions } from "@/shared/api/generated/view/view";
import {
  Command,
  CommandDialog,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/shared/components/ui/command";

const DEBOUNCE_MS = 200;

/** 結果の 1 件目が選ばれるのを待つ最大のフレーム数 */
const SELECTION_WAIT_FRAMES = 30;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: string;
  ref?: string;
  onResultSelect: (path: string) => void;
};

type StatusProps = {
  sent: string;
  pending: boolean;
  error: unknown;
  total: number | undefined;
  revision: string | undefined;
};

/** 件数・読み込み中・失敗・一致なしの文言（変わるたびに読み上げる） */
const SearchStatus = ({
  sent,
  pending,
  error,
  total,
  revision,
}: StatusProps) => {
  let text = "";
  if (sent !== "") {
    if (error instanceof AppError)
      text = error.problem?.detail ?? error.message;
    else if (pending && total === undefined) text = "検索しています";
    else if (total === 0)
      text = "該当する文書はありません。別の語を試してください。";
    else if (total !== undefined)
      text = `${total} 件${revision ? `（リビジョン ${revision}）` : ""}`;
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

/** 開いている配信元・リビジョンの文書を語で探すダイアログ */
export const SearchDialog = ({
  open,
  onOpenChange,
  source,
  ref: revision,
  onResultSelect,
}: Props) => {
  const [query, setQuery] = useState("");
  const [sent, setSent] = useState("");

  // 入力の 200 ミリ秒の待ちの後に問い合わせる
  useEffect(() => {
    const timer = setTimeout(() => setSent(query.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const search = useQuery({
    // eslint-disable-next-line react-hooks/refs -- `ref` は React の ref でなくリビジョンを指す props
    ...getViewSearchPageQueryOptions(source, { q: sent, ref: revision }),
    enabled: open && sent !== "",
  });
  const result = sent === "" ? undefined : search.data;

  // cmdk は最初に選んだ結果を `aria-activedescendant` に反映しないため、結果が出たら選んでいる結果を指す
  const inputRef = useRef<HTMLInputElement>(null);
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
  }, [result]);

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="文書を検索"
      description="語を入力して文書を探します"
    >
      <Command shouldFilter={false}>
        <CommandInput
          ref={inputRef}
          value={query}
          onValueChange={setQuery}
          placeholder="文書を検索"
        />
        <SearchStatus
          sent={sent}
          pending={search.isFetching}
          error={search.error}
          total={result?.totalCount}
          revision={revision}
        />
        <CommandList>
          {result && result.items.length > 0 && (
            <CommandGroup>
              {result.items.map((item) => (
                <CommandItem
                  key={item.path}
                  value={item.path}
                  onSelect={() => {
                    onResultSelect(item.path);
                    onOpenChange(false);
                  }}
                  className="flex-col items-start gap-1"
                >
                  <span className="font-medium">{item.name}</span>
                  <code className="font-mono text-xs text-muted-foreground">
                    {item.path}
                  </code>
                  {item.snippets.slice(0, 1).map((snippet) => (
                    <span
                      key={snippet}
                      className="text-xs text-muted-foreground"
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
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  );
};
