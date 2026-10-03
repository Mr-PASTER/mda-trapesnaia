import { describe, expect, it } from "vitest";
import {
  addDays,
  formatDayFull,
  formatDayShort,
  formatWeekdayShort,
  iso,
  parseIso,
  rangeIso,
} from "../src/lib/dates";

describe("dates", () => {
  it("round-trips iso without timezone shifts", () => {
    expect(iso(parseIso("2026-10-03"))).toBe("2026-10-03");
  });

  it("formats the short date in Russian", () => {
    expect(formatDayShort("2026-10-03")).toBe("3 октября");
    expect(formatDayShort("2026-05-01")).toBe("1 мая");
  });

  it("formats weekday short", () => {
    expect(formatWeekdayShort("2026-10-03")).toBe("Сб");
  });

  it("formats the full date with weekday", () => {
    expect(formatDayFull("2026-10-12")).toBe("Понедельник, 12 октября 2026");
  });

  it("adds days and builds a range", () => {
    expect(addDays("2026-10-03", 2)).toBe("2026-10-05");
    expect(rangeIso("2026-10-03", "2026-10-06")).toEqual([
      "2026-10-03",
      "2026-10-04",
      "2026-10-05",
      "2026-10-06",
    ]);
    expect(rangeIso("2026-10-03", "2026-10-02")).toEqual([]);
  });
});
