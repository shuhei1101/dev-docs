import { defineConfig } from "orval";

const input = { target: "./openapi.json" };

export default defineConfig({
  api: {
    input,
    output: {
      mode: "tags-split",
      target: "./src/shared/api/generated/api.ts",
      schemas: "./src/shared/api/generated/model",
      client: "react-query",
      httpClient: "fetch",
      mock: true,
      clean: true,
      override: {
        fetch: { includeHttpResponseReturnType: false },
        mutator: { path: "./src/shared/adapters/api-client.ts", name: "apiClient" },
      },
    },
  },
  zod: {
    input,
    output: {
      mode: "tags-split",
      target: "./src/shared/api/generated/zod",
      client: "zod",
      fileExtension: ".zod.ts",
    },
  },
});
