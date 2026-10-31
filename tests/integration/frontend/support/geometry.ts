import type { Locator, Page } from "@playwright/test";

/** 要素の位置と大きさ。画面に出ていないときは例外にする */
export const boxOf = async (locator: Locator) => {
  const box = await locator.boundingBox();
  if (box === null) throw new Error("要素が画面に出ていません");
  return box;
};

/** ビューポートの大きさ */
export const viewportOf = (page: Page) => {
  const size = page.viewportSize();
  if (size === null) throw new Error("ビューポートがありません");
  return size;
};
