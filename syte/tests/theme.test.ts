import { describe, expect, it } from "vitest";
import { resolveTheme, STORAGE_KEY } from "../src/lib/theme";
import { applyTheme, getStoredTheme, storeTheme } from "../src/lib/theme";

describe("resolveTheme", () => {
  it("returns explicit themes as-is", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
  it("resolves system from prefers-color-scheme", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
});

describe("stored theme", () => {
  it("defaults to system and round-trips", () => {
    window.localStorage.clear();
    expect(getStoredTheme()).toBe("system");
    storeTheme("dark");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("dark");
    expect(getStoredTheme()).toBe("dark");
  });
});

describe("theme selection", () => {
  it("persists the choice and toggles the html class", () => {
    document.documentElement.classList.remove("dark");
    storeTheme("dark");
    applyTheme(getStoredTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    storeTheme("light");
    applyTheme(getStoredTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
