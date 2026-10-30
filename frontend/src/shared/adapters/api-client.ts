import { AppError } from "@/shared/core/app-error";

/** orval が生成した API の関数が通る fetch。失敗を AppError にするのはここだけ */
export const apiClient = async <T>(url: string, init: RequestInit = {}): Promise<T> => {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined && init.body !== null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(url, { ...init, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new AppError("通信に失敗しました。", 0);
  }
  if (!response.ok) throw await AppError.fromResponse(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
};

export default apiClient;
