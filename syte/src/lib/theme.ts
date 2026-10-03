import { readLocal, writeLocal } from "./storage";

export type Theme = "light" | "dark" | "system";
export const STORAGE_KEY = "mda.theme";

export function getStoredTheme(): Theme {
  const raw = readLocal(STORAGE_KEY);
  return raw === "light" || raw === "dark" || raw === "system" ? raw : "system";
}

export function storeTheme(theme: Theme): void {
  writeLocal(STORAGE_KEY, theme);
}

export function resolveTheme(theme: Theme, prefersDark: boolean): "light" | "dark" {
  if (theme === "system") return prefersDark ? "dark" : "light";
  return theme;
}

export function applyTheme(theme: Theme): void {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolved = resolveTheme(theme, prefersDark);
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

export function subscribeSystemTheme(cb: () => void): () => void {
  const mql = window.matchMedia("(prefers-color-scheme: dark)");
  mql.addEventListener("change", cb);
  return () => mql.removeEventListener("change", cb);
}
