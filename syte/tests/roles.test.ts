import { describe, expect, it } from "vitest";
import { participatesInMeals } from "../src/lib/roles";

describe("participatesInMeals", () => {
  it("eater и admin участвуют", () => {
    expect(participatesInMeals("eater")).toBe(true);
    expect(participatesInMeals("admin")).toBe(true);
  });
  it("operator и accountant не участвуют", () => {
    expect(participatesInMeals("operator")).toBe(false);
    expect(participatesInMeals("accountant")).toBe(false);
  });
  it("пустая или неизвестная роль не участвует", () => {
    expect(participatesInMeals(undefined)).toBe(false);
    expect(participatesInMeals("")).toBe(false);
    expect(participatesInMeals("guest")).toBe(false);
  });
});
