import js from "@eslint/js";
import betterTailwindcss from "eslint-plugin-better-tailwindcss";
import boundaries from "eslint-plugin-boundaries";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

const SRC = "frontend/src";

export default tseslint.config(
  {
    ignores: [
      "src/dev_docs/screen/**",
      "frontend/src/shared/api/generated/**",
      "frontend/src/route-tree.gen.ts",
      "node_modules/**",
      "tmp/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["frontend/**/*.{ts,tsx}", "tests/unit/frontend/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { projectService: false },
    },
    plugins: {
      "react-hooks": reactHooks,
      "jsx-a11y": jsxA11y,
      boundaries,
      "better-tailwindcss": betterTailwindcss,
    },
    settings: {
      "better-tailwindcss": { entryPoint: `${SRC}/index.css` },
      "boundaries/elements": [
        { type: "app", pattern: `${SRC}/app/**` },
        { type: "routes", pattern: `${SRC}/routes/**` },
        { type: "features", pattern: `${SRC}/features/**` },
        { type: "shared", pattern: `${SRC}/shared/**` },
        { type: "testing", pattern: `${SRC}/testing/**` },
      ],
      "boundaries/include": [`${SRC}/**`],
      "import/resolver": { typescript: { project: "frontend/tsconfig.json" } },
    },
    rules: {
      ...reactHooks.configs["recommended-latest"].rules,
      "jsx-a11y/tabindex-no-positive": "error",
      "jsx-a11y/no-noninteractive-tabindex": "error",
      "jsx-a11y/interactive-supports-focus": "error",
      "jsx-a11y/click-events-have-key-events": "error",
      "jsx-a11y/no-autofocus": "error",
      "jsx-a11y/alt-text": "error",
      "jsx-a11y/anchor-is-valid": "error",
      "jsx-a11y/label-has-associated-control": "error",
      "jsx-a11y/no-static-element-interactions": "error",
      "boundaries/dependencies": [
        "error",
        {
          default: "allow",
          policies: [
            {
              from: { element: { type: "shared" } },
              disallow: {
                to: {
                  element: { types: { anyOf: ["app", "routes", "features"] } },
                },
              },
            },
            {
              from: { element: { type: "features" } },
              disallow: {
                to: { element: { types: { anyOf: ["app", "routes"] } } },
              },
            },
            {
              from: { element: { type: "testing" } },
              disallow: {
                to: {
                  element: { types: { anyOf: ["app", "routes", "features"] } },
                },
              },
            },
          ],
        },
      ],
      "better-tailwindcss/no-unregistered-classes": "off",
      "better-tailwindcss/enforce-consistent-variable-syntax": "off",
      complexity: ["error", 15],
      "func-style": ["error", "expression"],
      "@typescript-eslint/consistent-type-definitions": ["error", "type"],
      "@typescript-eslint/no-non-null-assertion": "error",
      "no-restricted-syntax": [
        "error",
        { selector: "TSEnumDeclaration", message: "enum は使わない" },
      ],
    },
  },
  {
    // shadcn/ui のコピーは任意値を含むため検査から外す
    files: [`${SRC}/**/*.{ts,tsx}`],
    ignores: [`${SRC}/shared/components/ui/**`],
    rules: {
      "better-tailwindcss/no-restricted-classes": [
        "error",
        { restrict: [{ pattern: "\\[.+\\]" }] },
      ],
    },
  },
  {
    files: [`${SRC}/shared/components/ui/**`],
    rules: {
      "func-style": "off",
      "react-hooks/refs": "off",
      "jsx-a11y/label-has-associated-control": "off",
      "jsx-a11y/click-events-have-key-events": "off",
      "jsx-a11y/no-static-element-interactions": "off",
    },
  },
  {
    files: ["frontend/*.ts", "eslint.config.js"],
    languageOptions: { globals: globals.node },
  },
);
