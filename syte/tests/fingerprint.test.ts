import { webcrypto } from "node:crypto";
import { beforeEach, describe, expect, it } from "vitest";
import { getDeviceFingerprint, resetDeviceId } from "../src/api/fingerprint";

// jsdom does not implement WebCrypto's `subtle`; polyfill it for hashing.
if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, "crypto", {
    value: webcrypto,
    configurable: true,
    writable: true,
  });
}

describe("device fingerprint", () => {
  beforeEach(() => resetDeviceId());

  it("is a stable 64-char hex string", async () => {
    const a = await getDeviceFingerprint();
    const b = await getDeviceFingerprint();
    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(a).toBe(b);
  });

  it("is stored on the device", async () => {
    await getDeviceFingerprint();
    expect(window.localStorage.getItem("mda.device")).toBeTruthy();
  });
});
