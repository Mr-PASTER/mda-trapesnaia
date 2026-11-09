import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export type HallBrief = { id: string; name: string };

export type TemplateGroup = { id?: string; name: string; show_subtotal: boolean; hall_ids: string[] };
export type TemplateTotal = { id?: string; name: string; all_halls: boolean; hall_ids: string[] };
export type ReportTemplate = { groups: TemplateGroup[]; totals: TemplateTotal[] };

export const useReportTemplate = () =>
  useQuery({
    queryKey: ["report-template"],
    queryFn: () => apiFetch<ReportTemplate>("/report-template"),
  });

export const useSaveReportTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportTemplate) =>
      apiFetch<ReportTemplate>("/report-template", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report-template"] }),
  });
};

export const useCatalogHalls = () =>
  useQuery({
    queryKey: ["catalog", "halls"],
    queryFn: () => apiFetch<HallBrief[]>("/catalog/halls"),
  });
