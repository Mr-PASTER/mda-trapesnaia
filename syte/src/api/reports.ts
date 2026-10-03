import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type DailyReport = components["schemas"]["DailyReportOut"];
export type PeriodReport = components["schemas"]["PeriodReportOut"];
export type MealReport = components["schemas"]["MealReportOut"];

function hallQuery(hallId?: string): string {
  return hallId ? `&hall_id=${hallId}` : "";
}

export function fetchDailyReport(date: string, hallId?: string): Promise<DailyReport> {
  return apiFetch<DailyReport>(`/accountant/report?date=${date}${hallQuery(hallId)}`);
}

export function fetchPeriodReport(from: string, to: string, hallId?: string): Promise<PeriodReport> {
  return apiFetch<PeriodReport>(`/accountant/report/period?from=${from}&to=${to}${hallQuery(hallId)}`);
}

export function useDailyReport(date: string, hallId?: string) {
  return useQuery({
    queryKey: ["report", "daily", date, hallId ?? "all"],
    queryFn: () => fetchDailyReport(date, hallId),
  });
}

export function usePeriodReport(from: string, to: string, hallId?: string) {
  return useQuery({
    queryKey: ["report", "period", from, to, hallId ?? "all"],
    queryFn: () => fetchPeriodReport(from, to, hallId),
  });
}

export function dailyExportUrl(date: string, hallId?: string): string {
  return `/api/v1/accountant/report/export?date=${date}${hallQuery(hallId)}`;
}

export function periodExportUrl(from: string, to: string, hallId?: string): string {
  return `/api/v1/accountant/report/period/export?from=${from}&to=${to}${hallQuery(hallId)}`;
}
