import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: [
    "@storybook/addon-a11y",
    "@storybook/addon-themes",
    "msw-storybook-addon",
  ],
  framework: "@storybook/react-vite",
  staticDirs: ["./public"],
  viteFinal: (viteConfig) => ({
    ...viteConfig,
    // 画面の配信用のビルド設定（出力先・ルート生成）は Storybook に持ち込まない
    plugins: (viteConfig.plugins ?? []).filter(
      (plugin) =>
        !(
          plugin &&
          "name" in plugin &&
          String(plugin.name).includes("tanstack-router")
        ),
    ),
  }),
};

export default config;
