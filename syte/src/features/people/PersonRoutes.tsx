import { useParams } from "react-router";
import { MenuPage } from "../menu/MenuPage";
import { SettingsPage } from "../settings/SettingsPage";
import { useCurrentUser } from "../../api/auth";

export function PersonMenuPage() {
  const { userId = "" } = useParams();
  const { data: me } = useCurrentUser();
  return <MenuPage target={{ mode: "admin", userId }} readOnly={me?.role === "operator"} />;
}

export function PersonSettingsPage() {
  const { userId = "" } = useParams();
  const { data: me } = useCurrentUser();
  return <SettingsPage target={{ mode: "admin", userId }} readOnly={me?.role === "operator"} />;
}
