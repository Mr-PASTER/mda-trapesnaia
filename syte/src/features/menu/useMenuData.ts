import { useMyCalendar, useSaveMyDay } from "../../api/me";
import { useSaveUserDay, useUserCalendar } from "../../api/admin";

export type Target = { mode: "self" } | { mode: "admin"; userId: string };

export function useMenuDays(target: Target, from: string, to: string) {
  const isSelf = target.mode === "self";
  const self = useMyCalendar(from, to, isSelf);
  const admin = useUserCalendar(target.mode === "admin" ? target.userId : "", from, to, !isSelf);
  return isSelf ? self : admin;
}

export function useSaveMenuDay(target: Target) {
  const self = useSaveMyDay();
  const admin = useSaveUserDay(target.mode === "admin" ? target.userId : "");
  return target.mode === "self" ? self : admin;
}
