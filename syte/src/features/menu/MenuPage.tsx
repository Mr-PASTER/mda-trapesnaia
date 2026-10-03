import { useState } from "react";
import { useNavigate } from "react-router";
import { useMealTypes } from "../../api/catalog";
import { todayIso, addDays } from "../../lib/dates";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { DayGrid } from "./DayGrid";
import { DayEditModal } from "./DayEditModal";
import { useMenuDays, useSaveMenuDay, type Target } from "./useMenuData";
import type { DayState } from "../../api/me";

export function MenuPage({ target }: { target: Target }) {
  const navigate = useNavigate();
  const from = todayIso();
  const to = addDays(from, 30);
  const { data: days, isLoading, isError } = useMenuDays(target, from, to);
  const { data: mealTypes = [] } = useMealTypes();
  const save = useSaveMenuDay(target);
  const [opened, setOpened] = useState<DayState | null>(null);

  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{target.mode === "self" ? "Моё меню" : "Меню питающегося"}</h1>
        {target.mode === "admin" && (
          <button onClick={() => navigate("/people")} className="min-h-11 rounded-xl border border-border px-3 text-sm">
            ← К списку
          </button>
        )}
      </header>

      {isLoading && <Spinner />}
      {isError && <p className="text-sm font-medium text-accent">Не удалось загрузить календарь</p>}
      {days && days.length === 0 && (
        <EmptyState title="Календарь ещё не сформирован" hint="Дни появятся после генерации расписания" />
      )}
      {days && days.length > 0 && <DayGrid days={days} mealTypes={mealTypes} onOpen={setOpened} />}

      {opened && (
        <DayEditModal
          day={opened}
          mealTypes={mealTypes}
          onClose={() => setOpened(null)}
          onSave={(date, body) => save.mutateAsync({ date, body })}
        />
      )}
    </div>
  );
}
