import type { components } from "../api/schema";

type DayLike = Pick<components["schemas"]["DayStateOut"], "available" | "editable">;
type ItemLike = Pick<components["schemas"]["MealStateOut"], "is_served" | "is_going">;

export type TileStatus = "absent" | "locked" | "editable";
export type MealStatus = "going" | "not_going" | "not_served";

export function tileStatus(day: DayLike): TileStatus {
  if (!day.available) return "absent";
  return day.editable ? "editable" : "locked";
}

export function mealStatus(item: ItemLike): MealStatus {
  if (!item.is_served) return "not_served";
  return item.is_going ? "going" : "not_going";
}
