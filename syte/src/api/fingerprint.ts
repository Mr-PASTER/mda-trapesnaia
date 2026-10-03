import { readLocal, writeLocal } from "../lib/storage";

const DEVICE_KEY = "mda.device";
let cached: string | null = null;

async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function deviceId(): string {
  let id = readLocal(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    writeLocal(DEVICE_KEY, id);
  }
  return id;
}

export async function getDeviceFingerprint(): Promise<string> {
  if (cached) return cached;
  cached = await sha256Hex(`${deviceId()}:${navigator.userAgent}`);
  return cached;
}

export function resetDeviceId(): void {
  cached = null;
  try {
    window.localStorage.removeItem(DEVICE_KEY);
  } catch {
    /* ignore */
  }
}
