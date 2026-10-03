import { useParams } from "react-router";
import { MenuPage } from "../menu/MenuPage";
import { SettingsPage } from "../settings/SettingsPage";

export function PersonMenuPage() {
  const { userId = "" } = useParams();
  return <MenuPage target={{ mode: "admin", userId }} />;
}

export function PersonSettingsPage() {
  const { userId = "" } = useParams();
  return <SettingsPage target={{ mode: "admin", userId }} />;
}
