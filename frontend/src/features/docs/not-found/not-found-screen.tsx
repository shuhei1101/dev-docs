import { Link, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useState } from "react";

import { describeMissing } from "@/features/docs/not-found/missing";
import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import { useViewListRefs } from "@/shared/api/generated/view/view";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { Topbar } from "@/shared/components/topbar/topbar";
import { buttonVariants } from "@/shared/components/ui/button";
import { MissingSchema } from "@/shared/core/schema";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { cn } from "@/shared/lib/utils";
import { usePreferencesStore } from "@/shared/stores/preferences";

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

type Props = {
  /** `notFound` の `data`（文書の取得の problem） */
  data?: unknown;
};

/** 見つからない画面。URL を変えずに、見つからなかったものと次のリンクを出す */
export const NotFoundScreen = ({ data }: Props) => {
  const params = useParams({ strict: false }) as { source?: string };
  const search = useSearch({ strict: false }) as { rev?: string };
  const navigate = useNavigate();
  const [searchOpen, setSearchOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const { colorScheme, singleKeyShortcuts, setColorScheme } = usePreferencesStore();

  const kind = MissingSchema.safeParse(data).data?.missing;
  const source = kind === "source" || kind === "not_served" ? undefined : params.source;
  const settings = useSettingsGetSettingsSources().data;
  const refs = useViewListRefs(source ?? "", undefined, {
    query: { enabled: source !== undefined && kind !== undefined },
  }).data;

  const serving = (settings?.sources ?? []).filter((item) => item.status === "serving" && item.id);
  const configs = settings?.sources.find((item) => item.id === params.source)?.config;
  const missing = describeMissing(data, {
    defaultRef: refs?.defaultRef,
    configs,
    source: params.source,
    ref: refs?.git === false ? undefined : (search.rev ?? refs?.defaultRef),
  });
  const primary = missing.kind === "source" || missing.kind === "not_served";

  useShortcut("search", () => setSearchOpen(true), {
    enabled: source !== undefined && !searchOpen && !helpOpen,
  });
  useShortcut("help", () => setHelpOpen(true), { enabled: !searchOpen && !helpOpen });

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-background focus:p-2"
      >
        本文へスキップ
      </a>
      <Topbar
        screen="not-found"
        sources={serving.map((item) => ({
          id: item.id as string,
          writable: item.scope.write === null || (item.scope.write?.length ?? 0) > 0,
        }))}
        currentSource={source}
        refs={source ? refs : undefined}
        currentRef={search.rev}
        colorScheme={colorScheme}
        onSourceSelect={(id) => void navigate({ to: "/$source", params: { source: id } })}
        onRefSelect={(rev) =>
          source && void navigate({ to: "/$source", params: { source }, search: { rev } })
        }
        onSearchOpen={() => setSearchOpen(true)}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <main id="main" tabIndex={-1} className="mx-auto max-w-2xl space-y-4 p-8">
        <h1 className="text-2xl font-semibold">{missing.heading}</h1>
        <p className="text-muted-foreground">{missing.description}</p>
        {missing.details.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {missing.details.map((detail, index) => (
              <div key={`${detail.label}:${index}`} className="contents">
                <dt className="font-medium">{detail.label}</dt>
                <dd className="font-mono text-xs break-all">{detail.value}</dd>
              </div>
            ))}
          </dl>
        )}
        <div className="flex flex-wrap gap-2">
          {(missing.kind === "doc" || missing.kind === "ref") && params.source && (
            <Link
              to="/$source"
              params={{ source: params.source }}
              search={missing.kind === "doc" ? { rev: search.rev } : {}}
              className={buttonVariants()}
            >
              {params.source} のトップを開く
            </Link>
          )}
          <Link
            to="/_settings"
            className={cn(buttonVariants({ variant: primary ? "default" : "outline" }))}
          >
            設定を開く
          </Link>
        </div>
        {primary && serving.length > 0 && (
          <ul aria-label="配信中の配信元" className="flex flex-wrap gap-2">
            {serving.map((item) => (
              <li key={item.id}>
                <Link
                  to="/$source"
                  params={{ source: item.id as string }}
                  className="font-mono text-sm text-primary hover:underline"
                >
                  {item.id}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
      {source !== undefined && (
        <SearchDialog
          open={searchOpen}
          onOpenChange={setSearchOpen}
          source={source}
          ref={missing.kind === "ref" ? undefined : search.rev}
          onResultSelect={(path) =>
            void navigate({
              to: "/$source/$",
              params: { source, _splat: path },
              search: { rev: search.rev },
            })
          }
        />
      )}
      <ShortcutDialog
        open={helpOpen}
        onOpenChange={setHelpOpen}
        screen="not-found"
        singleKey={singleKeyShortcuts}
      />
    </div>
  );
};
