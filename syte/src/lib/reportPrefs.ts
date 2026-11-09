import { readLocal, writeLocal } from "./storage";

const KEY = "mda.report.reserve";

export function readReservePref(): boolean {
  return readLocal(KEY) === "1";
}

export function writeReservePref(value: boolean): void {
  writeLocal(KEY, value ? "1" : "0");
}
