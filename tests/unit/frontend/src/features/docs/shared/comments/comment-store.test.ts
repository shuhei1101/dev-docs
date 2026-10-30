import { beforeEach, expect, test } from "vitest";

import { commentsOf, useCommentStore } from "@/features/docs/shared/comments/comment-store";

const input = (docId: string, body: string) => ({
  docId,
  source: "s",
  ref: "main",
  path: "a.md",
  docTitle: "A",
  headings: [],
  quote: `引用 ${body}`,
  prefix: "前",
  suffix: "後",
  body,
});

beforeEach(() => {
  useCommentStore.setState({ comments: [] });
});

test("test_comments_of", () => {
  const { add } = useCommentStore.getState();
  add(input("s@main:a.md", "1"));
  add(input("s@main:b.md", "2"));
  add(input("s@main:a.md", "3"));

  const result = commentsOf(useCommentStore.getState().comments, "s@main:a.md");

  expect(result.map((item) => item.body)).toEqual(["1", "3"]);
  expect(result[0]).toMatchObject({ quote: "引用 1", prefix: "前", suffix: "後" });
});
