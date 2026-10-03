import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { MealType } from "./auth";

export function fetchMealTypes(): Promise<MealType[]> {
  return apiFetch<MealType[]>("/catalog/meal-types");
}

export function useMealTypes() {
  return useQuery({
    queryKey: ["meal-types"],
    queryFn: fetchMealTypes,
    staleTime: 5 * 60_000,
  });
}
