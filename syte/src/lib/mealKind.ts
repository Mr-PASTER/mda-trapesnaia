import type { components } from "../api/schema";

export type MealKind = components["schemas"]["MealKind"];

export const MEAL_ORDER: MealKind[] = ["breakfast", "lunch", "snack", "dinner"];

export const MEAL_LABEL: Record<MealKind, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  snack: "Полдник",
  dinner: "Ужин",
};
