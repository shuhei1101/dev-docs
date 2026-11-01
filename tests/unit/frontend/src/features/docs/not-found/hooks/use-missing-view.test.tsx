import { screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import { useMissingView } from "@/features/docs/not-found/hooks/use-missing-view";
import { refsResponse, settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderInRouter } from "@tests/helpers/render";

type MissingView = ReturnType<typeof useMissingView>;

const useHandlers = () => {
  const refs = vi.fn(() => HttpResponse.json(refsResponse()));
  server.use(
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(settingsView([settingsSource("s"), settingsSource("t")])),
    ),
    http.get("/_api/sources/:source/refs", refs),
  );
  return refs;
};

/** フックの戻り値を外へ渡すだけの部品 */
const Probe = ({ data, onRender }: { data: unknown; onRender: (view: MissingView) => void }) => {
  onRender(useMissingView(data));
  return <p>probe</p>;
};

const renderMissingView = async (data: unknown, path: string) => {
  const holder: { current?: MissingView } = {};
  renderInRouter(<Probe data={data} onRender={(view) => (holder.current = view)} />, path);
  await screen.findByText("probe");
  return holder as Required<typeof holder>;
};

test("test_use_missing_view", async () => {
  const refs = useHandlers();

  const view = await renderMissingView({ missing: "doc", value: "a.md" }, "/s/a.md");

  await waitFor(() => expect(view.current.serving).toHaveLength(2));
  await waitFor(() => expect(view.current.refs).toBeDefined());
  expect(view.current.source).toBe("s");
  expect(view.current.missing.kind).toBe("doc");
  expect(refs).toHaveBeenCalled();
});

test("test_use_missing_view_when_source_missing", async () => {
  const refs = useHandlers();

  const view = await renderMissingView({ missing: "source", value: "unknown" }, "/unknown");

  await waitFor(() => expect(view.current.serving).toHaveLength(2));
  expect(view.current.source).toBeUndefined();
  expect(view.current.urlSource).toBe("unknown");
  expect(refs).not.toHaveBeenCalled();
});
