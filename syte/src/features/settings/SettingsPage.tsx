import { DefaultsForm } from "../defaults/DefaultsForm";
import { ThemeSection } from "../theme/ThemeSection";
import type { Target } from "../../lib/target";

export function SettingsPage({ target }: { target: Target }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">
        {target.mode === "self" ? "Настройки" : "Настройки питающегося"}
      </h1>
      <DefaultsForm target={target} />
      <ThemeSection />
    </div>
  );
}
