/**
 * Typed client for the OASIS FastAPI backend.
 *
 * The backend streams long-running work as Server-Sent Events over POST, so
 * `EventSource` cannot be used (it only does GET): `streamPost` reads the
 * response body with a streaming reader and parses `data:` frames itself.
 */

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Extract FastAPI's `detail` field, falling back to raw text. */
async function readError(response: Response): Promise<ApiError> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const text = await response.text();
    if (text) {
      try {
        const parsed = JSON.parse(text);
        const fromDetail = parsed?.detail;
        detail =
          typeof fromDetail === "string"
            ? fromDetail
            : JSON.stringify(fromDetail ?? parsed);
      } catch {
        detail = text.slice(0, 500);
      }
    }
  } catch {
    /* keep the status line */
  }
  return new ApiError(response.status, detail);
}

async function request<T>(
  path: string,
  init: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    throw new ApiError(
      0,
      `Cannot reach the OASIS backend at ${API_BASE}. Start it with ` +
        `\`uvicorn backend.main:app\` from the OASIS directory. (${
          error instanceof Error ? error.message : String(error)
        })`,
    );
  }

  if (!response.ok) {
    throw await readError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "GET", signal, cache: "no-store" });
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
    signal,
  });
}

export type StreamEvent = {
  type?: string;
  stage?: string;
  percent?: number;
  message?: string;
  [key: string]: unknown;
};

/**
 * POST a JSON body and invoke `onEvent` for every SSE frame.
 *
 * Resolves when the stream ends; rejects with `ApiError` when the connection
 * fails before any frame arrives (after that, backend errors arrive as
 * `{type: "error"}` events so the dashboard can show them inline).
 */
export async function streamPost(
  path: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body ?? {}),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) return;
    throw new ApiError(
      0,
      `Cannot reach the OASIS backend at ${API_BASE}. Start it with ` +
        `\`uvicorn backend.main:app\` from the OASIS directory. (${
          error instanceof Error ? error.message : String(error)
        })`,
    );
  }

  if (!response.ok) {
    throw await readError(response);
  }
  if (!response.body) {
    throw new ApiError(0, "The backend returned an empty response stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        for (const line of frame.split("\n")) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const payload = trimmed.slice(5).trim();
          if (!payload) continue;
          let event: StreamEvent;
          try {
            event = JSON.parse(payload) as StreamEvent;
          } catch {
            // Ignore malformed frames rather than killing the stream.
            continue;
          }
          // Called outside the parse try/catch so errors thrown by the
          // consumer (e.g. backend `{error: ...}` events) propagate to
          // the caller instead of being silently swallowed here.
          onEvent(event);
        }
      }
    }
  } catch (error) {
    if (signal?.aborted) return;
    throw error;
  } finally {
    reader.releaseLock();
  }
}
