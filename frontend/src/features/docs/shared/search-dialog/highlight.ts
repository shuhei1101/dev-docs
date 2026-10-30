export type HighlightPart = { text: string; match: boolean };

const escape = (word: string): string => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** 抜粋を、語に一致する箇所とそれ以外の並びに分ける（つなぐと `text` に戻る） */
export const splitHighlight = (text: string, query: string): HighlightPart[] => {
  const words = query.split(/\s+/).filter((word) => word !== "");
  if (words.length === 0) return [{ text, match: false }];
  const pattern = new RegExp(`(${words.map(escape).join("|")})`, "gi");
  return text
    .split(pattern)
    .map((part, index) => ({ text: part, match: index % 2 === 1 }))
    .filter((part) => part.text !== "");
};
