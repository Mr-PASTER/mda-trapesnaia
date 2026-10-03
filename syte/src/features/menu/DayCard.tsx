import { MealTypeIcon } from "../../components/ui/MealTypeIcon";
import { Icon } from "../../components/ui/Icon";
import { mealStatus, tileStatus } from "../../lib/dayStatus";
import { formatDayShort, formatWeekdayShort } from "../../lib/dates";
import { MEAL_ORDER } from "../../lib/mealKind";
import type { DayState } from "../../api/me";
import type { MealType } from "../../api/auth";

const STICK: Record<string, string> = {
  going: "bg-ink",
  not_going: "bg-muted/70",
  not_served: "bg-border",
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
      ? "border-dashed border-accent/60 text-muted"
      : status === "locked"
        ? "border-border bg-sunken"
        : "border-border bg-surface shadow-card hover:border-accent/60";

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
        <MealTypeIcon icon={type.icon} title={type.name} className="absolute right-2 top-2 h-5 w-5 text-muted" />
      )}

      {status === "absent" ? (
        <span className="text-[11px] font-medium text-accent">Дня нет</span>
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
        <Icon name="lock" title="Приём закрыт" className="absolute bottom-2 right-2 h-3.5 w-3.5 text-lock" />
      )}
    </button>
  );
}
