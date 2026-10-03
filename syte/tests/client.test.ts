import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError, ConflictError, setUnauthorizedHandler } from "../src/api/client";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("sends fingerprint header and parses json", async () => {
    const fetchMock = mockFetch(200, { ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const res = await apiFetch<{ ok: boolean }>("/catalog/meal-types");
    expect(res.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/v1/catalog/meal-types");
    expect((init.headers as Headers).get("X-Device-Fingerprint")).toMatch(/^[0-9a-f]{64}$/);
    expect(init.credentials).toBe("same-origin");
  });

  it("calls unauthorized handler on 401", async () => {
    vi.stubGlobal("fetch", mockFetch(401, { detail: "invalid_session" }));
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    await expect(apiFetch("/me")).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalled();
  });

  it("throws ConflictError with current payload on 409", async () => {
    vi.stubGlobal("fetch", mockFetch(409, { detail: "record_changed", current: { date: "2026-10-03" } }));
    await expect(apiFetch("/me/days/2026-10-03", { method: "PUT" })).rejects.toBeInstanceOf(ConflictError);
  });
});
