import { DayCard } from "./DayCard";
import type { DayState } from "../../api/me";
import type { MealType } from "../../api/auth";

export function DayGrid({
  days,
  mealTypes,
  onOpen,
}: {
  days: DayState[];
  mealTypes: MealType[];
  onOpen: (day: DayState) => void;
}) {
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7 xl:grid-cols-8">
      {days.map((day) => (
        <DayCard key={day.date} day={day} mealTypes={mealTypes} onOpen={onOpen} />
      ))}
    </div>
  );
}
