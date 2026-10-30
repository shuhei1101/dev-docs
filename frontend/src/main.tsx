import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppProviders } from "@/app/providers";
import { createQueryClient } from "@/app/query-client";
import { createAppRouter } from "@/app/router";
import "@/index.css";

const queryClient = createQueryClient();
const router = createAppRouter({ queryClient });

const root = document.getElementById("root");
if (root === null) throw new Error("#root がありません");

createRoot(root).render(
  <StrictMode>
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
);
