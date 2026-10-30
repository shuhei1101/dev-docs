import { Link } from "@tanstack/react-router";
import {
  ChevronDown,
  GitBranch,
  GitCompare,
  MessageSquare,
  Moon,
  PanelLeft,
  Search,
  Settings,
  Sun,
} from "lucide-react";

import type { RefsResponse } from "@/shared/api/generated/model";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import type { ScreenId } from "@/shared/core/shortcuts";
import type { ColorScheme } from "@/shared/stores/preferences";

type Props = {
  screen: ScreenId;
  sources?: { id: string; writable: boolean }[];
  currentSource?: string;
  refs?: RefsResponse;
  currentRef?: string;
  commentCount?: number;
  colorScheme: ColorScheme;
  onSourceSelect?: (id: string) => void;
  onRefSelect?: (ref: string) => void;
  onCompareStart?: () => void;
  onSearchOpen?: () => void;
  onCommentPanelToggle?: () => void;
  onSidebarOpen?: () => void;
  onColorSchemeToggle: () => void;
};

type SourceMenuProps = Pick<
  Props,
  "sources" | "currentSource" | "onSourceSelect"
>;

const SourceMenu = ({
  sources = [],
  currentSource,
  onSourceSelect,
}: SourceMenuProps) => (
  <DropdownMenu>
    <DropdownMenuTrigger
      render={
        <Button variant="outline" size="sm" aria-label="配信元を切り替える" />
      }
    >
      <span className="font-mono text-xs">{currentSource ?? "配信元"}</span>
      <ChevronDown />
    </DropdownMenuTrigger>
    <DropdownMenuContent>
      <DropdownMenuGroup>
        <DropdownMenuLabel>配信元</DropdownMenuLabel>
        {sources.map((source) => (
          <DropdownMenuItem
            key={source.id}
            onClick={() => onSourceSelect?.(source.id)}
          >
            <span className="font-mono text-xs">{source.id}</span>
            <span className="ml-auto text-xs text-muted-foreground">
              {source.writable ? "読み書き" : "読み取りだけ"}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuGroup>
    </DropdownMenuContent>
  </DropdownMenu>
);

type RefMenuProps = Required<Pick<Props, "refs" | "screen">> &
  Pick<Props, "currentRef" | "onRefSelect" | "onCompareStart">;

const RefMenu = ({
  refs,
  screen,
  currentRef,
  onRefSelect,
  onCompareStart,
}: RefMenuProps) => {
  const branches = [
    refs.defaultRef,
    ...(refs.branches ?? []).map((item) => item.name),
  ].filter((name, index, all) => all.indexOf(name) === index);
  const tags = refs.tags ?? [];
  const commits = refs.commits ?? [];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            aria-label="リビジョンを切り替える"
          />
        }
      >
        <GitBranch />
        <span className="hidden font-mono text-xs md:inline">
          {currentRef ?? refs.defaultRef}
        </span>
        <ChevronDown />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="max-h-96 overflow-y-auto">
        <DropdownMenuGroup>
          <DropdownMenuLabel>ブランチ</DropdownMenuLabel>
          {branches.map((name) => (
            <DropdownMenuItem
              key={`b:${name}`}
              onClick={() => onRefSelect?.(name)}
            >
              <span className="font-mono text-xs">{name}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
        {tags.length > 0 && (
          <DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>タグ</DropdownMenuLabel>
            {tags.map((tag) => (
              <DropdownMenuItem
                key={`t:${tag.name}`}
                onClick={() => onRefSelect?.(tag.name)}
              >
                <span className="font-mono text-xs">{tag.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        )}
        {commits.length > 0 && (
          <DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>最近の commit</DropdownMenuLabel>
            {commits.map((commit) => (
              <DropdownMenuItem
                key={`c:${commit.commit}`}
                onClick={() => onRefSelect?.(commit.commit)}
              >
                <span className="font-mono text-xs">{commit.commit}</span>
                <span className="ml-2 truncate text-xs text-muted-foreground">
                  {commit.subject}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        )}
        {screen === "doc-view" && (
          <DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onCompareStart}>
              <GitCompare />
              別のリビジョンと比較
            </DropdownMenuItem>
          </DropdownMenuGroup>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const HomeLink = ({ currentSource }: { currentSource?: string }) =>
  currentSource !== undefined ? (
    <Link
      to="/$source"
      params={{ source: currentSource }}
      className="font-semibold tracking-tight"
    >
      dev-docs
    </Link>
  ) : (
    <Link to="/" className="font-semibold tracking-tight">
      dev-docs
    </Link>
  );

/** 3 画面に共通のトップバー。配信元・リビジョンの切り替え、検索、コメント、設定、明暗の切り替え */
export const Topbar = (props: Props) => {
  const { screen, currentSource, refs, commentCount = 0, colorScheme } = props;
  const settings = screen === "settings";
  const showRefs =
    !settings && currentSource !== undefined && refs?.git === true;
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border bg-background px-3">
      {screen === "doc-view" && (
        <Button
          variant="ghost"
          size="icon"
          aria-label="文書の一覧を開く"
          className="md:hidden"
          onClick={props.onSidebarOpen}
        >
          <PanelLeft />
        </Button>
      )}
      <HomeLink currentSource={currentSource} />
      {settings && <span className="text-sm text-muted-foreground">設定</span>}
      {!settings && <SourceMenu {...props} />}
      {showRefs && refs && <RefMenu {...props} refs={refs} />}
      <div className="ml-auto flex items-center gap-1">
        {!settings && (
          <Button
            variant="outline"
            size="sm"
            aria-label="検索"
            onClick={props.onSearchOpen}
          >
            <Search />
            <span className="hidden text-muted-foreground md:inline">検索</span>
          </Button>
        )}
        {screen === "doc-view" && (
          <Button
            variant="ghost"
            size="sm"
            aria-label="コメント"
            onClick={props.onCommentPanelToggle}
          >
            <MessageSquare />
            {commentCount > 0 && (
              <span className="text-xs">{commentCount}</span>
            )}
          </Button>
        )}
        {!settings && (
          <Button
            variant="ghost"
            size="icon"
            aria-label="設定"
            render={<Link to="/_settings" />}
            nativeButton={false}
          >
            <Settings />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          aria-label="明暗を切り替える"
          aria-pressed={colorScheme !== "system"}
          onClick={props.onColorSchemeToggle}
        >
          {colorScheme === "dark" ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  );
};
