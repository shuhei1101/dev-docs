import type { RefsResponse } from "@/shared/api/generated/model";
import { Button } from "@/shared/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

type Props = {
  base: string;
  head: string;
  refs: RefsResponse;
  onChange: (next: { base: string; rev: string }) => void;
  onClear: () => void;
};

/** リビジョンのメニューと同じ並び（`defaultRef`・ブランチ・タグ・最近の commit）。一覧に無い値は先頭に足す */
const choices = (refs: RefsResponse, current: string): string[] => {
  const all = [
    refs.defaultRef,
    ...(refs.branches ?? []).map((item) => item.name),
    ...(refs.tags ?? []).map((item) => item.name),
    ...(refs.commits ?? []).map((item) => item.commit),
  ];
  const unique = [...new Set(all)];
  return unique.includes(current) ? unique : [current, ...unique];
};

type PickerProps = {
  label: string;
  value: string;
  options: string[];
  onValueChange: (value: string) => void;
};

const Picker = ({ label, value, options, onValueChange }: PickerProps) => (
  <Select
    value={value}
    onValueChange={(next) => next !== null && onValueChange(next)}
  >
    <SelectTrigger aria-label={label} className="w-44 font-mono text-xs">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {options.map((option) => (
        <SelectItem key={option} value={option} className="font-mono text-xs">
          {option}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

/** 差分を強調していることと、比べている 2 つのリビジョンの案内 */
export const DiffBanner = ({ base, head, refs, onChange, onClear }: Props) => (
  <section
    aria-label="差分"
    className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted px-3 py-2 text-sm"
  >
    <span className="text-muted-foreground">比較元</span>
    <Picker
      label="比較元"
      value={base}
      options={choices(refs, base)}
      onValueChange={(next) => onChange({ base: next, rev: head })}
    />
    <span aria-hidden="true">→</span>
    <span className="text-muted-foreground">比較先</span>
    <Picker
      label="比較先"
      value={head}
      options={choices(refs, head)}
      onValueChange={(next) => onChange({ base, rev: next })}
    />
    <Button variant="outline" size="sm" className="ml-auto" onClick={onClear}>
      差分の強調を解除
    </Button>
  </section>
);
