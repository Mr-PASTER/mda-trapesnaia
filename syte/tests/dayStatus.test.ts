import { describe, expect, it } from "vitest";
import { mealStatus, tileStatus } from "../src/lib/dayStatus";

describe("tileStatus", () => {
  it("marks non-generated days as absent", () => {
    expect(tileStatus({ available: false, editable: false })).toBe("absent");
    expect(tileStatus({ available: false, editable: true })).toBe("absent");
  });
  it("marks days past the deadline as locked", () => {
    expect(tileStatus({ available: true, editable: false })).toBe("locked");
  });
  it("marks editable days", () => {
    expect(tileStatus({ available: true, editable: true })).toBe("editable");
  });
});

describe("mealStatus", () => {
  it("handles not served", () => {
    expect(mealStatus({ is_served: false, is_going: true })).toBe("not_served");
  });
  it("handles going and not going", () => {
    expect(mealStatus({ is_served: true, is_going: true })).toBe("going");
    expect(mealStatus({ is_served: true, is_going: false })).toBe("not_going");
  });
});
