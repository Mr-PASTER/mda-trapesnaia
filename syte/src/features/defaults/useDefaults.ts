import { useMyDefaults, useSaveMyDefaults } from "../../api/me";
import { useSaveUserDefaults, useUserDefaults } from "../../api/admin";
import type { Target } from "../../lib/target";

export function useDefaults(target: Target) {
  const isSelf = target.mode === "self";
  const self = useMyDefaults(isSelf);
  const admin = useUserDefaults(target.mode === "admin" ? target.userId : "", !isSelf);
  return isSelf ? self : admin;
}

export function useSaveDefaults(target: Target) {
  const isSelf = target.mode === "self";
  const self = useSaveMyDefaults();
  const admin = useSaveUserDefaults(target.mode === "admin" ? target.userId : "");
  return isSelf ? self : admin;
}
