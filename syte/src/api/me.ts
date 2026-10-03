import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type DayState = components["schemas"]["DayStateOut"];
export type DayUpdate = components["schemas"]["DayUpdateRequest"];
export type Defaults = components["schemas"]["DefaultsOut"];

export function fetchMyCalendar(from: string, to: string): Promise<DayState[]> {
  return apiFetch<DayState[]>(`/me/calendar?from=${from}&to=${to}`);
}

export function saveMyDay(date: string, body: DayUpdate): Promise<DayState> {
  return apiFetch<DayState>(`/me/days/${date}`, { method: "PUT", body: JSON.stringify(body) });
}

export function fetchMyDefaults(): Promise<Defaults> {
  return apiFetch<Defaults>("/me/defaults");
}

export function saveMyDefaults(body: components["schemas"]["DefaultsUpdate"]): Promise<Defaults> {
  return apiFetch<Defaults>("/me/defaults", { method: "PUT", body: JSON.stringify(body) });
}

export function useMyCalendar(from: string, to: string) {
  return useQuery({ queryKey: ["calendar", "me", from, to], queryFn: () => fetchMyCalendar(from, to) });
}

export function useSaveMyDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, body }: { date: string; body: DayUpdate }) => saveMyDay(date, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calendar"] }),
  });
}
