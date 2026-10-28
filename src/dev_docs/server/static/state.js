/** サーバーが画面に埋め込む状態の型と読み取り。 */
/** `#page-state` の JSON を読む。 */
export function readPageState() {
    const element = document.getElementById("page-state");
    return JSON.parse(element?.textContent ?? "{}");
}
