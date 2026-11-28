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

const addThree = () => {
  const { add } = useCommentStore.getState();
  for (const body of ["1", "2", "3"]) {
    add(input("s@main:a.md", body));
  }
  return useCommentStore.getState().comments;
};

test("test_remove", () => {
  const before = addThree();

  const removed = useCommentStore.getState().remove(before[1].id);

  expect(useCommentStore.getState().comments.map((item) => item.body)).toEqual(["1", "3"]);
  expect(removed).toEqual({ comment: before[1], index: 1 });
});

test("test_remove_when_missing", () => {
  const before = addThree();

  const removed = useCommentStore.getState().remove("missing");

  expect(useCommentStore.getState().comments).toEqual(before);
  expect(removed).toBeNull();
});

test("test_restore", () => {
  const before = addThree();
  const removed = useCommentStore.getState().remove(before[1].id);

  if (removed) useCommentStore.getState().restore(removed.comment, removed.index);

  expect(useCommentStore.getState().comments).toEqual(before);
});

test("test_restore_when_exists", () => {
  const before = addThree();
  const removed = useCommentStore.getState().remove(before[1].id);

  if (removed) {
    useCommentStore.getState().restore(removed.comment, removed.index);
    useCommentStore.getState().restore(removed.comment, removed.index);
  }

  expect(useCommentStore.getState().comments.filter((item) => item.id === before[1].id)).toHaveLength(1);
});
