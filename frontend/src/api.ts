/** Thin API client. Dev proxy forwards /api -> backend, so paths are backend paths. */

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

let bearer = localStorage.getItem("festos_token") ?? "";

export function setToken(token: string) {
  bearer = token;
  if (token) localStorage.setItem("festos_token", token);
  else localStorage.removeItem("festos_token");
}

export function getToken() {
  return bearer;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (bearer) headers.Authorization = `Bearer ${bearer}`;
  const res = await fetch(BASE + path, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
      else detail = JSON.stringify(body);
    } catch {
      /* non-JSON error body -> keep the status text */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** POST with the mandatory reason field most write endpoints demand. */
export function apiWrite<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return api<T>(path, { method: "POST", body });
}
