import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type Me = components["schemas"]["MeOut"];
export type MealType = components["schemas"]["MealTypeOut"];

export function login(login: string, password: string): Promise<Me> {
  return apiFetch<Me>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login, password }),
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function fetchMe(): Promise<Me> {
  return apiFetch<Me>("/auth/me");
}

export function useCurrentUser() {
  return useQuery({ queryKey: ["me"], queryFn: fetchMe, retry: false });
}
