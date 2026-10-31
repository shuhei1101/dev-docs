import type { NavTab } from "@/shared/api/generated/model";

type Props = {
  tab: NavTab;
  index: number;
  ref: string | null;
};

/** 選んだタブに文書が無いことの表示 */
export const EmptyTab = ({ tab, index, ref }: Props) => (
  <div className="space-y-2 py-8">
    <h2 className="text-lg font-semibold">{tab.title}の文書はありません</h2>
    <p className="text-sm text-muted-foreground">
      {`このタブの nav.tabs[${index}].paths に当たる文書が${ref === null ? "" : `、リビジョン ${ref}`} にありません。`}
    </p>
  </div>
);
