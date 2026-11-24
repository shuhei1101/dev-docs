import { Link } from "@tanstack/react-router";
import { ChevronRight, Circle, Minus, Plus, SearchX } from "lucide-react";
import { useState } from "react";

import type { NavItem, NavTab } from "@/shared/api/generated/model";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import { cn } from "@/shared/lib/utils";

type Props = {
  tab: NavTab;
  source: string;
  currentPath: string | null;
  search: DocViewSearch;
  onNavigate?: () => void;
};

const MARKERS = {
  added: { Icon: Plus, label: "追加" },
  modified: { Icon: Circle, label: "変更" },
  deleted: { Icon: Minus, label: "削除" },
} as const;

const Marker = ({ change }: { change: NonNullable<NavItem["change"]> }) => {
  const { Icon, label } = MARKERS[change];
  return (
    <Icon
      aria-label={label}
      role="img"
      className={cn(
        "size-3 shrink-0",
        change === "modified" && "fill-current",
        change === "added" && "text-success",
        change === "modified" && "text-warning",
        change === "deleted" && "text-destructive",
      )}
    />
  );
};

type ItemsProps = Omit<Props, "tab"> & { items: NavItem[] };

/** group の配下（入れ子の group を含む）に、開いている文書の page があるか */
const containsPath = (items: NavItem[], path: string | null): boolean =>
  path !== null &&
  items.some((item) =>
    item.kind === "group"
      ? containsPath(item.items ?? [], path)
      : item.path === path,
  );

type GroupProps = Omit<ItemsProps, "items"> & { group: NavItem };

/** 見出しを押すと配下の page を折りたたむ・開く group。開いている文書を含む group は開いて始める */
const Group = ({ group, ...rest }: GroupProps) => {
  const children = group.items ?? [];
  const [open, setOpen] = useState(() =>
    containsPath(children, rest.currentPath),
  );
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="mt-3 mb-1 flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-xs font-semibold text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <ChevronRight
          aria-hidden="true"
          className={cn(
            "size-3.5 shrink-0 transition-transform motion-reduce:transition-none",
            open && "rotate-90",
          )}
        />
        <span className="min-w-0 break-words">{group.title}</span>
      </button>
      {open && (
        <div className="pl-3">
          <Items {...rest} items={children} />
        </div>
      )}
    </li>
  );
};

const Items = ({
  items,
  source,
  currentPath,
  search,
  onNavigate,
}: ItemsProps) => (
  <ul className="space-y-0.5">
    {items.map((item) =>
      item.kind === "group" ? (
        <Group
          key={`group:${item.title}`}
          group={item}
          source={source}
          currentPath={currentPath}
          search={search}
          onNavigate={onNavigate}
        />
      ) : (
        <li key={`page:${item.path}`}>
          <Link
            to="/$source/$"
            params={{ source, _splat: item.path ?? "" }}
            search={
              item.change === "deleted"
                ? { rev: search.base, tab: search.tab }
                : { rev: search.rev, base: search.base, tab: search.tab }
            }
            aria-current={item.path === currentPath ? "page" : undefined}
            onClick={onNavigate}
            className={cn(
              "flex items-center justify-between gap-2 rounded-md px-2 py-1 text-sm hover:bg-accent",
              item.path === currentPath && "bg-accent font-medium",
              item.excluded && "text-muted-foreground",
            )}
          >
            <span className={cn(item.change === "deleted" && "line-through")}>
              {item.title}
            </span>
            <span className="flex shrink-0 items-center gap-1">
              {item.excluded && (
                <SearchX
                  aria-label="検索から除外"
                  role="img"
                  className="size-3 shrink-0"
                >
                  <title>検索から除外</title>
                </SearchX>
              )}
              {item.change != null && <Marker change={item.change} />}
            </span>
          </Link>
        </li>
      ),
    )}
  </ul>
);

/** 選んでいるタブの文書の一覧（サイドバーとドロワーの中身） */
export const DocSidebar = ({ tab, ...rest }: Props) => (
  <nav aria-label="文書の一覧">
    <Items {...rest} items={tab.items} />
  </nav>
);
