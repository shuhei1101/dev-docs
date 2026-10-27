/** コメントの引用と起票画面の URL。 */

export const QUOTE_MAX = 30;
export const QUOTE_KEEP = 12;
export const ISSUE_URL_MAX = 8000;
export const ISSUE_TRUNCATED =
  "\n\n…（長さの上限を超えたため、本文の末尾を切り詰めました。全文はクリップボードにコピーしています）";

/** `QUOTE_MAX` を超える引用を先頭と末尾の `QUOTE_KEEP` 字と `…` にする。 */
export function shortenQuote(text: string): string {
  throw new Error("not implemented");
}

/** `ISSUE_URL_MAX` に収まるまで本文の末尾を切り詰めた起票画面の URL を返す。 */
export function fitIssueUrl(
  repository: string,
  labels: string[],
  title: string,
  body: string,
): string {
  throw new Error("not implemented");
}
