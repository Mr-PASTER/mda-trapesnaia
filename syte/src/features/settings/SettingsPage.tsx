import { Link } from "react-router";
import { useCurrentUser } from "../../api/auth";
import { DefaultsForm } from "../defaults/DefaultsForm";
import { ThemeSection } from "../theme/ThemeSection";
import { participatesInMeals } from "../../lib/roles";
import type { Target } from "../../lib/target";

export function SettingsPage({ target, readOnly = false }: { target: Target; readOnly?: boolean }) {
  const { data: me } = useCurrentUser();
  const showDefaults =
    target.mode === "self" ? participatesInMeals(me?.role) : true;
  const showTheme = target.mode === "self";

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">
          {target.mode === "self" ? "Настройки" : "Настройки питающегося"}
        </h1>
        {target.mode === "admin" && (
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/people"
              className="min-h-11 rounded-xl border border-border px-3 text-sm leading-11"
            >
              ← К списку
            </Link>
            <Link
              to={`/people/${target.userId}`}
              className="min-h-11 rounded-xl border border-border px-3 text-sm leading-11"
            >
              Меню
            </Link>
          </div>
        )}
      </header>
      {readOnly ? (
        <p className="rounded-2xl border border-border bg-surface p-4 text-sm text-muted">
          Просмотр: оператор не редактирует питание питающегося.
        </p>
      ) : (
        showDefaults && <DefaultsForm target={target} />
      )}
      {showTheme && <ThemeSection />}
    </div>
  );
}
