import { Link } from "@tanstack/react-router";

import type { MissingDescription } from "@/features/docs/not-found/missing";
import type { ServingSource } from "@/features/docs/shared/serving-sources";
import { buttonVariants } from "@/shared/components/ui/button";

type Props = {
  missing: MissingDescription;
  source?: string;
  rev?: string;
  serving: ServingSource[];
};

/** 次のリンク（配信元のトップ・設定画面）と、代わりに開ける配信中の配信元 */
export const MissingLinks = ({ missing, source, rev, serving }: Props) => {
  const primary = missing.kind === "source" || missing.kind === "not_served";
  const hasTop =
    (missing.kind === "doc" || missing.kind === "ref") && source !== undefined;
  return (
    <>
      <div className="flex flex-wrap gap-2">
        {hasTop && (
          <Link
            to="/$source"
            params={{ source }}
            search={missing.kind === "doc" ? { rev } : {}}
            className={buttonVariants()}
          >
            {source} のトップを開く
          </Link>
        )}
        <Link
          to="/_settings"
          className={buttonVariants({
            variant: primary ? "default" : "outline",
          })}
        >
          設定を開く
        </Link>
      </div>
      {serving.length > 0 && (
        <ul aria-label="配信中の配信元" className="flex flex-wrap gap-2">
          {serving.map((item) => (
            <li key={item.id}>
              <Link
                to="/$source"
                params={{ source: item.id }}
                className="font-mono text-sm text-primary hover:underline"
              >
                {item.id}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
};
