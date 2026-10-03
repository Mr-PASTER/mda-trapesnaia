import { useEffect, useState } from "react";
import { useMealTypes } from "../../api/catalog";
import { useToast } from "../../components/ui/Toast";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { MEAL_LABEL, MEAL_ORDER, type MealKind } from "../../lib/mealKind";
import { useDefaults, useSaveDefaults } from "./useDefaults";
import type { Target } from "../../lib/target";

export function DefaultsForm({ target }: { target: Target }) {
  const toast = useToast();
  const { data: mealTypes = [] } = useMealTypes();
  const { data, isLoading } = useDefaults(target);
  const save = useSaveDefaults(target);

  const [mealTypeId, setMealTypeId] = useState<string | null>(null);
  const [meals, setMeals] = useState<Record<MealKind, boolean>>({
    breakfast: false,
    lunch: false,
    snack: false,
    dinner: false,
  });

  useEffect(() => {
    if (!data) return;
    setMealTypeId(data.default_meal_type_id ?? null);
    setMeals({
      breakfast: data.meals.breakfast ?? false,
      lunch: data.meals.lunch ?? false,
      snack: data.meals.snack ?? false,
      dinner: data.meals.dinner ?? false,
    });
  }, [data]);

  async function submit() {
    try {
      await save.mutateAsync({ default_meal_type_id: mealTypeId, meals });
      toast("Сохранено");
    } catch {
      toast("Не удалось сохранить");
    }
  }

  if (isLoading) return <Spinner />;

  const segment = "min-h-11 rounded-xl px-4 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <h2 className="mb-3 text-base font-semibold">Мои приёмы по умолчанию</h2>

      <p className="mb-2 text-sm text-muted">Тип питания по умолчанию</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {mealTypes.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setMealTypeId(t.id)}
            aria-pressed={mealTypeId === t.id}
            className={`${segment} ${
              mealTypeId === t.id ? "bg-accent text-on-accent" : "border border-border text-ink hover:bg-sunken"
            }`}
          >
            {t.name}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        {MEAL_ORDER.map((kind) => (
          <div key={kind} className="flex items-center justify-between gap-3">
            <span className="text-sm">{MEAL_LABEL[kind]}</span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMeals((m) => ({ ...m, [kind]: true }))}
                className={`${segment} ${
                  meals[kind] ? "bg-accent text-on-accent" : "border border-border text-ink hover:bg-sunken"
                }`}
              >
                Идёт
              </button>
              <button
                type="button"
                onClick={() => setMeals((m) => ({ ...m, [kind]: false }))}
                className={`${segment} ${
                  !meals[kind] ? "bg-solid text-on-solid" : "border border-border text-ink hover:bg-sunken"
                }`}
              >
                Не идёт
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex justify-end">
        <Button onClick={submit} disabled={save.isPending}>
          {save.isPending ? "Сохраняем…" : "Сохранить"}
        </Button>
      </div>
    </section>
  );
}
