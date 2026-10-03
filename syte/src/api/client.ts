import { getDeviceFingerprint } from "./fingerprint";
import type { components } from "./schema";

const API_BASE = "/api/v1";

type DayState = components["schemas"]["DayStateOut"];

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export class ConflictError extends ApiError {
  current: DayState | undefined;
  constructor(detail: unknown, current: DayState | undefined) {
    super(409, detail);
    this.current = current;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const fingerprint = await getDeviceFingerprint();
  const headers = new Headers(init.headers);
  headers.set("X-Device-Fingerprint", fingerprint);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });

  if (response.status === 401) {
    onUnauthorized?.();
    throw new ApiError(401, "unauthorized");
  }

  let payload: unknown = undefined;
  if (response.status !== 204) {
    const text = await response.text();
    payload = text ? JSON.parse(text) : undefined;
  }

  if (!response.ok) {
    const detail = (payload as { detail?: unknown })?.detail ?? `HTTP ${response.status}`;
    if (response.status === 409) {
      throw new ConflictError(detail, (payload as { current?: DayState })?.current);
    }
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}
