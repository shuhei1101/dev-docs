/** サーバーが画面に埋め込む状態の型と読み取り。 */

/** 文書の画面・見つからない画面の状態（フィールドはサーバーの `PageState`）。 */
export type PageState = {
  source_id: string | null;
  sources: { id: string; title: string; note: string }[];
  git: boolean;
  ref: string | null;
  ref_in_url: string | null;
  default_ref: string | null;
  doc_page: string | null;
  diff: {
    ref: string;
    commit: string;
    date: string;
    current_commit: string;
    current_date: string;
  } | null;
  github_repository: string | null;
  issue_labels: string[];
  table_keys: string[];
  hidden_columns: Record<string, string[]>;
};

/** `#page-state` の JSON を読む。 */
export function readPageState<T = PageState>(): T {
  const element = document.getElementById("page-state");
  return JSON.parse(element?.textContent ?? "{}") as T;
}
