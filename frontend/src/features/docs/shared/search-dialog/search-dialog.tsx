import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { splitHighlight } from "@/features/docs/shared/search-dialog/highlight";
import { getViewSearchPageQueryOptions } from "@/shared/api/generated/view/view";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/shared/components/ui/command";

const DEBOUNCE_MS = 200;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: string;
  ref?: string;
  onResultSelect: (path: string) => void;
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

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="文書を検索"
      description="語を入力して文書を探します"
    >
      <Command shouldFilter={false}>
        <CommandInput
          value={query}
          onValueChange={setQuery}
          placeholder="文書を検索"
        />
        <CommandList>
          {sent !== "" && result && result.items.length === 0 && (
            <CommandEmpty>一致する文書がありません。</CommandEmpty>
          )}
          {result && result.items.length > 0 && (
            <CommandGroup heading={`${result.totalCount} 件`}>
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
