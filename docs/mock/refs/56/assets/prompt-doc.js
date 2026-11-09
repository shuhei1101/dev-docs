// PR #56 のプロンプトの文書のモック
// 変換が出した Markdown（<script type="text/markdown" data-doc>）を、実際の画面と同じく mdmark で本文に描く
// 開く文書は ?doc= で選ぶ（無ければ最初の文書）

import { mount } from "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@580fae8/dist/index.js";

const sources = [...document.querySelectorAll('script[type="text/markdown"][data-doc]')];
const requested = new URLSearchParams(location.search).get("doc");
const current = sources.find((source) => source.dataset.doc === requested) ?? sources[0];

// タイトル・パンくず・パスを、開いた文書の値に差し替える
for (const el of document.querySelectorAll("[data-doc-text]")) {
  el.textContent = current.dataset[el.dataset.docText];
}
document.title = `${current.dataset.title} | sample | dev-docs`;

// サイドバーは開いた文書の行を選択中にする
for (const link of document.querySelectorAll("[data-doc-link]")) {
  if (link.dataset.docLink === current.dataset.doc) {
    link.setAttribute("aria-current", "page");
  } else {
    link.removeAttribute("aria-current");
  }
}

/** 本文の ## と ### から、右の目次を作り直す */
function buildToc(body) {
  const list = document.getElementById("toc-list");
  const items = [...body.querySelectorAll("h2[id], h3[id]")].map((heading) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = `#${heading.id}`;
    link.textContent = heading.textContent.trim();
    // ### は 1 レイヤー下げて見せる
    if (heading.tagName === "H3") item.className = "toc__sub";
    item.append(link);
    return item;
  });
  list.replaceChildren(...items);
}

const body = document.getElementById("doc");
// 実際の画面と同じく、Markdown の最初の # は画面のタイトルが代わりに出す
const markdown = current.textContent.replace(/^\s*# [^\n]*\n/, "");

// 本文の見出しが描かれたら（描き直されたら）目次を作る
new MutationObserver(() => buildToc(body)).observe(body, { childList: true, subtree: true });

mount(body, {
  markdown,
  docId: current.dataset.path,
  // モックではコメントを使わない
  commentStore: { load: async () => [], save: async ({ comment }) => ({ id: "mock", ...comment }) },
  config: { features: { comments: false } },
});
