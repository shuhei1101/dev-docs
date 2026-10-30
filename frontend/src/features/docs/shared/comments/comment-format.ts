import type { GitHubTarget } from "@/shared/api/generated/model";
import type { DocComment } from "@/features/docs/shared/comments/comment-store";

/** 非機能要件の `Issue の作成画面の URL の長さ` の決定値 */
export const ISSUE_URL_MAX = 7200;

/** 切り詰めた `body` の末尾に空行を挟んで付ける文 */
export const TRUNCATED_NOTE =
  "…（長さの上限を超えたため、本文の末尾を切り詰めました。全文はクリップボードにコピーしています）";

/** 選んだコメントを一覧の順に Markdown の本文にする */
export const formatComments = (comments: DocComment[]): string =>
  comments
    .map((comment) => {
      const trail = comment.headings.length > 0 ? comment.headings : ["冒頭"];
      const place = [comment.docTitle, ...trail].join(" › ");
      const location = `${comment.source}${comment.ref === null ? "" : ` @ ${comment.ref}`} : ${comment.path}`;
      const quote = comment.quote
        .split("\n")
        .map((line) => `> ${line}`)
        .join("\n");
      return [`### ${place}`, location, quote, comment.body].join("\n");
    })
    .join("\n\n");

const urlOf = (github: GitHubTarget, body: string): string => {
  const params = new URLSearchParams();
  if (github.issueLabels.length > 0) params.set("labels", github.issueLabels.join(","));
  params.set("body", body);
  return `https://github.com/${github.repository}/issues/new?${params.toString()}`;
};

/** サロゲートペアの途中で切らずに先頭の `length` 文字を取る */
const head = (text: string, length: number): string => Array.from(text).slice(0, length).join("");

/** `github` のリポジトリの Issue の作成画面の URL を、上限に収めて作る */
export const buildIssueUrl = (
  github: GitHubTarget,
  body: string,
): { url: string; truncated: boolean } => {
  const whole = urlOf(github, body);
  if (whole.length <= ISSUE_URL_MAX) return { url: whole, truncated: false };
  const suffix = `\n\n${TRUNCATED_NOTE}`;
  const length = Array.from(body).length;
  let low = 0;
  let high = length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (urlOf(github, head(body, middle) + suffix).length <= ISSUE_URL_MAX) low = middle;
    else high = middle - 1;
  }
  return { url: urlOf(github, head(body, low) + suffix), truncated: true };
};
