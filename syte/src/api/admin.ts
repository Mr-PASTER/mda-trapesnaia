import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { DayState, DayUpdate, Defaults } from "./me";
import type { components } from "./schema";

export type AdminUser = components["schemas"]["AdminUserOut"];

export function fetchPeople(hallId?: string): Promise<AdminUser[]> {
  const query = hallId ? `?hall_id=${hallId}` : "";
  return apiFetch<AdminUser[]>(`/admin/users${query}`);
}

export function fetchUserCalendar(userId: string, from: string, to: string): Promise<DayState[]> {
  return apiFetch<DayState[]>(`/admin/users/${userId}/calendar?from=${from}&to=${to}`);
}

export function saveUserDay(userId: string, date: string, body: DayUpdate): Promise<DayState> {
  return apiFetch<DayState>(`/admin/requests/${userId}/${date}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function fetchUserDefaults(userId: string): Promise<Defaults> {
  return apiFetch<Defaults>(`/admin/users/${userId}/defaults`);
}

export function saveUserDefaults(
  userId: string,
  body: components["schemas"]["DefaultsUpdate"],
): Promise<Defaults> {
  return apiFetch<Defaults>(`/admin/users/${userId}/defaults`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function usePeople(hallId?: string) {
  return useQuery({ queryKey: ["people", hallId ?? "all"], queryFn: () => fetchPeople(hallId) });
}

export function useUserCalendar(userId: string, from: string, to: string, enabled = true) {
  return useQuery({
    queryKey: ["calendar", "admin", userId, from, to],
    queryFn: () => fetchUserCalendar(userId, from, to),
    enabled,
  });
}

export function useSaveUserDay(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, body }: { date: string; body: DayUpdate }) => saveUserDay(userId, date, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calendar"] }),
  });
}

export function useUserDefaults(userId: string, enabled = true) {
  return useQuery({
    queryKey: ["defaults", "admin", userId],
    queryFn: () => fetchUserDefaults(userId),
    enabled,
  });
}

export function useSaveUserDefaults(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["DefaultsUpdate"]) => saveUserDefaults(userId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["defaults"] }),
  });
}
