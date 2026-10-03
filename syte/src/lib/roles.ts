/** Роли, которые участвуют в питании и ведут личные приёмы по умолчанию. */
const MEAL_ROLES = new Set(["eater", "admin"]);

export function participatesInMeals(role: string | undefined): boolean {
  return role !== undefined && MEAL_ROLES.has(role);
}
