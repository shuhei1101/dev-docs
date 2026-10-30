import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { MissingLinks } from "@/features/docs/not-found/components/missing-links";
import { useMissingView } from "@/features/docs/not-found/hooks/use-missing-view";
import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import { ShortcutDialog } from "@/shared/components/shortcut-dialog/shortcut-dialog";
import { Topbar } from "@/shared/components/topbar/topbar";
import { useShortcut } from "@/shared/hooks/use-shortcut";
import { usePreferencesStore } from "@/shared/stores/preferences";

const NEXT_SCHEME = { system: "dark", dark: "light", light: "dark" } as const;

type Props = {
  /** `notFound` の `data`（文書の取得の problem） */
  data?: unknown;
};

/** 見つからない画面。URL を変えずに、見つからなかったものと次のリンクを出す */
export const NotFoundScreen = ({ data }: Props) => {
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"search" | "help" | null>(null);
  const { colorScheme, singleKeyShortcuts, setColorScheme } =
    usePreferencesStore();
  const { source, urlSource, rev, refs, missing, serving } =
    useMissingView(data);

  const idle = dialog === null;
  useShortcut("search", () => setDialog("search"), {
    enabled: source !== undefined && idle,
  });
  useShortcut("help", () => setDialog("help"), { enabled: idle });

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
        sources={serving}
        currentSource={source}
        refs={source ? refs : undefined}
        currentRef={rev}
        colorScheme={colorScheme}
        onSourceSelect={(id) =>
          void navigate({ to: "/$source", params: { source: id } })
        }
        onRefSelect={(rev) =>
          source &&
          void navigate({ to: "/$source", params: { source }, search: { rev } })
        }
        onSearchOpen={() => setDialog("search")}
        onColorSchemeToggle={() => setColorScheme(NEXT_SCHEME[colorScheme])}
      />
      <main id="main" tabIndex={-1} className="mx-auto max-w-2xl space-y-4 p-8">
        <h1 className="text-2xl font-semibold">{missing.heading}</h1>
        <p className="text-muted-foreground">{missing.description}</p>
        {missing.details.length > 0 && (
          <dl className="space-y-1 text-sm">
            {missing.details.map((detail, index) => (
              <div key={`${detail.label}:${index}`} className="flex gap-4">
                <dt className="w-28 shrink-0 font-medium">{detail.label}</dt>
                <dd className="font-mono text-xs break-all">{detail.value}</dd>
              </div>
            ))}
          </dl>
        )}
        <MissingLinks
          missing={missing}
          source={urlSource}
          rev={rev}
          serving={serving}
        />
      </main>
      {source !== undefined && (
        <SearchDialog
          open={dialog === "search"}
          onOpenChange={(open) => setDialog(open ? "search" : null)}
          source={source}
          ref={missing.kind === "ref" ? undefined : rev}
          onResultSelect={(path) =>
            void navigate({
              to: "/$source/$",
              params: { source, _splat: path },
              search: { rev: rev },
            })
          }
        />
      )}
      <ShortcutDialog
        open={dialog === "help"}
        onOpenChange={(open) => setDialog(open ? "help" : null)}
        screen="not-found"
        singleKey={singleKeyShortcuts}
      />
    </div>
  );
};
