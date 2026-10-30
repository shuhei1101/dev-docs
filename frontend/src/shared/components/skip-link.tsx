/** キーボードでフォーカスしたときだけ見える、本文の領域へフォーカスを移すリンク */
export const SkipLink = () => (
  <a
    href="#main"
    onClick={(event) => {
      event.preventDefault();
      document.getElementById("main")?.focus();
    }}
    className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-background focus:p-2"
  >
    本文へスキップ
  </a>
);
