import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type Hall = components["schemas"]["HallOut"];
export type MealTypeRow = components["schemas"]["MealTypeOut"];
export type OperatorUser = components["schemas"]["OperatorUserOut"];

// --- Залы ---
export const useHalls = (onlyActive = false) =>
  useQuery({
    queryKey: ["op", "halls", onlyActive],
    queryFn: () => apiFetch<Hall[]>(`/operator/halls?only_active=${onlyActive}`),
  });

export const useCreateHall = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => apiFetch<Hall>("/operator/halls", { method: "POST", body: JSON.stringify({ name }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "halls"] }),
  });
};

export const useUpdateHall = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiFetch<Hall>(`/operator/halls/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "halls"] }),
  });
};

export const useDeleteHall = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/operator/halls/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "halls"] }),
  });
};

// --- Типы питания ---
export const useMealTypesAll = () =>
  useQuery({
    queryKey: ["op", "meal-types"],
    queryFn: () => apiFetch<MealTypeRow[]>("/operator/meal-types?only_active=false"),
  });

export const useCreateMealType = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; sort_order: number; icon: string | null }) =>
      apiFetch<MealTypeRow>("/operator/meal-types", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["op", "meal-types"] });
      qc.invalidateQueries({ queryKey: ["meal-types"] });
    },
  });
};

export const useUpdateMealType = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<MealTypeRow>(`/operator/meal-types/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["op", "meal-types"] });
      qc.invalidateQueries({ queryKey: ["meal-types"] });
    },
  });
};

export const useDeleteMealType = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/operator/meal-types/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "meal-types"] }),
  });
};

// --- Пользователи ---
export const useOperatorUsers = () =>
  useQuery({
    queryKey: ["op", "users"],
    queryFn: () => apiFetch<OperatorUser[]>("/operator/users?only_active=false"),
  });

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<OperatorUser>("/operator/users", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};

export const useUpdateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<OperatorUser>(`/operator/users/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};

export const useSetUserHalls = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, hallIds }: { id: string; hallIds: string[] }) =>
      apiFetch<OperatorUser>(`/operator/users/${id}/halls`, { method: "PUT", body: JSON.stringify({ hall_ids: hallIds }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};

export const useSetUserPassword = () =>
  useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      apiFetch<void>(`/operator/users/${id}/password`, { method: "PUT", body: JSON.stringify({ password }) }),
  });

export const useDeleteUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, hard }: { id: string; hard: boolean }) =>
      apiFetch<void>(`/operator/users/${id}?hard=${hard}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};
