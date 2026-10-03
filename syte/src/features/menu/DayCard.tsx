import { MealTypeIcon } from "../../components/ui/MealTypeIcon";
import { mealStatus, tileStatus } from "../../lib/dayStatus";
import { formatDayShort, formatWeekdayShort } from "../../lib/dates";
import { MEAL_ORDER } from "../../lib/mealKind";
import type { DayState } from "../../api/me";
import type { MealType } from "../../api/auth";

const STICK: Record<string, string> = {
  going: "bg-accent",
  not_going: "bg-not-going",
  not_served: "bg-muted/30",
};

export function DayCard({
  day,
  mealTypes,
  onOpen,
}: {
  day: DayState;
  mealTypes: MealType[];
  onOpen: (day: DayState) => void;
}) {
  const status = tileStatus(day);
  const type = mealTypes.find((t) => t.id === day.meal_type_id) ?? null;

  const frame =
    status === "absent"
      ? "border-absent/60 text-muted"
      : status === "locked"
        ? "border-border bg-surface/70"
        : "border-border bg-surface hover:border-accent/60";

  return (
    <button
      type="button"
      disabled={status !== "editable"}
      onClick={() => status === "editable" && onOpen(day)}
      className={`relative flex aspect-square min-h-24 flex-col items-start justify-between rounded-2xl border p-2.5 text-left transition ${frame} disabled:cursor-default`}
    >
      <span className="text-xs font-medium text-muted">{formatWeekdayShort(day.date)}</span>
      <span className="text-[15px] font-semibold leading-tight">{formatDayShort(day.date)}</span>

      {type && (
        <MealTypeIcon icon={type.icon} className="absolute right-2 top-2 h-4 w-4 text-muted" />
      )}

      {status === "absent" ? (
        <span className="text-[11px] font-medium text-absent">Дня нет</span>
      ) : (
        <span className="flex items-end gap-1" aria-hidden>
          {MEAL_ORDER.map((kind) => {
            const item = day.items.find((i) => i.meal_kind === kind);
            const cls = status === "locked" ? "bg-lock" : STICK[item ? mealStatus(item) : "not_served"];
            return <span key={kind} className={`h-5 w-[5px] rounded-full ${cls}`} />;
          })}
        </span>
      )}

      {status === "locked" && (
        <span className="absolute right-2 bottom-2 text-[11px] text-lock" title="Приём закрыт">🔒</span>
      )}
    </button>
  );
}
