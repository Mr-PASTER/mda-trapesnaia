import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./queryClient";
import { setUnauthorizedHandler } from "../api/client";
import { applyTheme, getStoredTheme, subscribeSystemTheme } from "../lib/theme";
import { ToastProvider } from "../components/ui/Toast";

function ThemeInitializer() {
  useEffect(() => {
    const stored = getStoredTheme();
    applyTheme(stored);
    if (stored !== "system") return;
    return subscribeSystemTheme(() => applyTheme("system"));
  }, []);
  return null;
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Не зацикливаемся: на странице входа 401 — это норма.
      if (window.location.pathname === "/login") return;
      window.location.assign("/login?reason=expired");
    });
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ThemeInitializer />
        {children}
      </ToastProvider>
    </QueryClientProvider>
  );
}
