import { getSettingsMock } from "@/shared/api/generated/settings/settings.msw";
import { getViewMock } from "@/shared/api/generated/view/view.msw";

/** 単体テスト・結合テスト・Storybook が使用する既定のハンドラ。各テストは `server.use` で上書きする */
export const handlers = [...getViewMock(), ...getSettingsMock()];
