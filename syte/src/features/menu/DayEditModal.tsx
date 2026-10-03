import { useState } from "react";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/Toast";
import { ApiError, ConflictError } from "../../api/client";
import { formatDayFull } from "../../lib/dates";
import { MEAL_LABEL, MEAL_ORDER, type MealKind } from "../../lib/mealKind";
import type { DayState, DayUpdate } from "../../api/me";
import type { MealType } from "../../api/auth";

function goingFrom(state: DayState): Record<MealKind, boolean> {
  return Object.fromEntries(
    MEAL_ORDER.map((k) => [k, state.items.find((i) => i.meal_kind === k)?.is_going ?? false]),
  ) as Record<MealKind, boolean>;
}

export function DayEditModal({
  day,
  mealTypes,
  onClose,
  onSave,
}: {
  day: DayState;
  mealTypes: MealType[];
  onClose: () => void;
  onSave: (date: string, body: DayUpdate) => Promise<DayState>;
}) {
  const toast = useToast();
  const [current, setCurrent] = useState<DayState>(day);
  const [mealTypeId, setMealTypeId] = useState(day.meal_type_id);
  const [going, setGoing] = useState<Record<MealKind, boolean>>(() => goingFrom(current));
  const [busy, setBusy] = useState(false);

  function applyState(next: DayState) {
    setCurrent(next);
    setMealTypeId(next.meal_type_id);
    setGoing(goingFrom(next));
  }

  async function submit() {
    setBusy(true);
    try {
      await onSave(current.date, { meal_type_id: mealTypeId, meals: going, version: current.version });
      onClose();
    } catch (err) {
      if (err instanceof ConflictError && err.current) {
        toast("Данные изменил администратор — обновляем значения");
        applyState(err.current);
      } else if (err instanceof ApiError && err.status === 403) {
        toast("День закрыт для правок");
        onClose();
      } else {
        toast("Не удалось сохранить");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={formatDayFull(current.date)} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {mealTypes.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setMealTypeId(t.id)}
              className={`min-h-11 rounded-xl px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                mealTypeId === t.id ? "bg-accent text-on-accent" : "border border-border text-ink hover:bg-sunken"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>

        {MEAL_ORDER.map((kind) => {
          const item = current.items.find((i) => i.meal_kind === kind);
          const served = item?.is_served ?? false;
          return (
            <div key={kind} className="flex items-center justify-between gap-3">
              <span className="text-sm">{MEAL_LABEL[kind]}</span>
              {served ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setGoing((g) => ({ ...g, [kind]: true }))}
                    className={`min-h-11 rounded-xl px-4 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                      going[kind] ? "bg-accent text-on-accent" : "border border-border text-ink hover:bg-sunken"
                    }`}
                  >
                    Идёт
                  </button>
                  <button
                    type="button"
                    onClick={() => setGoing((g) => ({ ...g, [kind]: false }))}
                    className={`min-h-11 rounded-xl px-4 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                      !going[kind] ? "bg-solid text-on-solid" : "border border-border text-ink hover:bg-sunken"
                    }`}
                  >
                    Не идёт
                  </button>
                </div>
              ) : (
                <span className="text-xs text-muted">не подаётся</span>
              )}
            </div>
          );
        })}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? "Сохраняем…" : "Сохранить"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
