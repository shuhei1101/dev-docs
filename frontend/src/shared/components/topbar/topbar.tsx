import { Link } from "@tanstack/react-router";
import {
  BookOpen,
  Database,
  FilePen,
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
import { Kbd } from "@/shared/components/ui/kbd";
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
  /** 開いている配信元の編集中の変更の件数 */
  pendingEditCount?: number;
  colorScheme: ColorScheme;
  onSourceSelect?: (id: string) => void;
  onRefSelect?: (ref: string) => void;
  onCompareStart?: () => void;
  onSearchOpen?: () => void;
  onCommentPanelToggle?: () => void;
  onPendingPanelToggle?: () => void;
  onSidebarOpen?: () => void;
  onColorSchemeToggle: () => void;
};

/** 配信元・リビジョンのメニューを、ボタンの幅を下限・画面の使用できる幅を上限にした中身の幅で開く */
const MENU_CONTENT_WIDTH =
  "w-auto min-w-(--anchor-width) max-w-(--available-width)";

/** メニューの項目を折り返さず 1 行で出す */
const MENU_ITEM_NOWRAP = "text-nowrap";

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
        <Button
          variant="outline"
          size="sm"
          className="px-1.5 md:px-2.5"
          aria-label={`配信元を切り替える${currentSource ? `。今は ${currentSource}` : ""}`}
        />
      }
    >
      <span className="max-w-16 truncate md:max-w-24 font-mono text-xs">
        {currentSource ?? "配信元"}
      </span>
      <ChevronDown className="hidden md:block" />
    </DropdownMenuTrigger>
    <DropdownMenuContent className={MENU_CONTENT_WIDTH}>
      <DropdownMenuGroup>
        <DropdownMenuLabel>配信元</DropdownMenuLabel>
        {sources.map((source) => (
          <DropdownMenuItem
            key={source.id}
            className={MENU_ITEM_NOWRAP}
            aria-current={source.id === currentSource ? "true" : undefined}
            onClick={() => onSourceSelect?.(source.id)}
          >
            <span className="truncate font-mono text-xs" title={source.id}>
              {source.id}
            </span>
            <span className="ml-auto shrink-0 text-xs text-muted-foreground">
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
  const current = currentRef ?? refs.defaultRef;
  const tags = refs.tags ?? [];
  const commits = refs.commits ?? [];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            className="px-1.5 md:px-2.5"
            aria-label={`リビジョンを切り替える。今は ${current}`}
          />
        }
      >
        <GitBranch />
        <span className="hidden font-mono text-xs md:inline">
          {currentRef ?? refs.defaultRef}
        </span>
        <ChevronDown className="hidden md:block" />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className={`${MENU_CONTENT_WIDTH} max-h-96 overflow-y-auto`}
      >
        <DropdownMenuGroup>
          <DropdownMenuLabel>ブランチ</DropdownMenuLabel>
          {branches.map((name) => (
            <DropdownMenuItem
              key={`b:${name}`}
              className={MENU_ITEM_NOWRAP}
              aria-current={name === current ? "true" : undefined}
              onClick={() => onRefSelect?.(name)}
            >
              <span className="truncate font-mono text-xs" title={name}>
                {name}
              </span>
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
                className={MENU_ITEM_NOWRAP}
                aria-current={tag.name === current ? "true" : undefined}
                onClick={() => onRefSelect?.(tag.name)}
              >
                <span className="truncate font-mono text-xs" title={tag.name}>
                  {tag.name}
                </span>
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
                className={MENU_ITEM_NOWRAP}
                aria-current={commit.commit === current ? "true" : undefined}
                onClick={() => onRefSelect?.(commit.commit)}
              >
                <span className="shrink-0 font-mono text-xs">
                  {commit.commit}
                </span>
                <span
                  className="ml-2 truncate text-xs text-muted-foreground"
                  title={commit.subject}
                >
                  {commit.subject}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        )}
        {screen === "doc-view" && (
          <DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className={MENU_ITEM_NOWRAP}
              onClick={onCompareStart}
            >
              <GitCompare />
              別のリビジョンと比較
            </DropdownMenuItem>
          </DropdownMenuGroup>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

type MetadataButtonsProps = {
  screen: ScreenId;
  currentSource?: string;
  pendingEditCount?: number;
  onPendingPanelToggle?: () => void;
};

/** 文書の画面とメタデータの画面で出す、メタデータの画面を開くボタンとレビュー中のパネルを開くボタン */
const MetadataButtons = ({
  screen,
  currentSource,
  pendingEditCount = 0,
  onPendingPanelToggle,
}: MetadataButtonsProps) => {
  if (screen !== "doc-view" && screen !== "metadata") return null;
  if (currentSource === undefined) return null;
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="px-1.5 md:px-2.5"
        aria-label="メタデータ"
        aria-current={screen === "metadata" ? "page" : undefined}
        render={
          <Link to="/$source/_metadata" params={{ source: currentSource }} />
        }
        nativeButton={false}
      >
        <Database />
        <span className="hidden md:inline">メタデータ</span>
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="px-1.5 md:px-2.5"
        aria-label={pendingEditCount > 0 ? `レビュー中 ${pendingEditCount} 件` : "レビュー中"}
        onClick={onPendingPanelToggle}
      >
        <FilePen />
        <span className="hidden md:inline">レビュー中</span>
        {pendingEditCount > 0 && (
          <span className="text-xs">{pendingEditCount}</span>
        )}
      </Button>
    </>
  );
};

const HOME_CLASS =
  "flex shrink-0 items-center gap-1.5 font-semibold tracking-tight whitespace-nowrap";

const HomeLabel = () => (
  <>
    <BookOpen className="size-4" aria-hidden="true" />
    <span className="sr-only md:not-sr-only">dev-docs</span>
  </>
);

const HomeLink = ({ currentSource }: { currentSource?: string }) =>
  currentSource !== undefined ? (
    <Link
      to="/$source"
      params={{ source: currentSource }}
      className={HOME_CLASS}
    >
      <HomeLabel />
    </Link>
  ) : (
    <Link to="/" className={HOME_CLASS}>
      <HomeLabel />
    </Link>
  );

/** 3 画面に共通のトップバー。配信元・リビジョンの切り替え、検索、コメント、設定、明暗の切り替え */
export const Topbar = (props: Props) => {
  const { screen, currentSource, refs, commentCount = 0, colorScheme } = props;

  const settings = screen === "settings";
  const showRefs =
    !settings && currentSource !== undefined && refs?.git === true;
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-1 border-b border-border bg-background px-2 md:gap-2 md:px-3">
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
            aria-label="検索 Ctrl K"
            aria-keyshortcuts="Control+K /"
            onClick={props.onSearchOpen}
          >
            <Search />
            <span className="hidden text-muted-foreground md:inline">検索</span>
            <Kbd className="hidden text-foreground md:inline-flex">Ctrl K</Kbd>
          </Button>
        )}
        {screen === "doc-view" && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={`コメント ${commentCount} 件`}
            onClick={props.onCommentPanelToggle}
          >
            <MessageSquare />
            {commentCount > 0 && (
              <span className="text-xs">{commentCount}</span>
            )}
          </Button>
        )}
        <MetadataButtons
          screen={screen}
          currentSource={currentSource}
          pendingEditCount={props.pendingEditCount}
          onPendingPanelToggle={props.onPendingPanelToggle}
        />
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
          aria-label="明暗を固定する"
          aria-pressed={colorScheme !== "system"}
          onClick={props.onColorSchemeToggle}
        >
          {colorScheme === "dark" ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  );
};
