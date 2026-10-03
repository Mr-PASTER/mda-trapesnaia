import { MEAL_LABEL, MEAL_ORDER } from "../../lib/mealKind";
import type { components } from "../../api/schema";

type MealReport = components["schemas"]["MealReportOut"];

export type ReportHallRow = {
  hallId: string;
  hallName: string;
  meals: MealReport[];
  total: number;
  reserveTotal: number;
};

const cell = "border-b border-border px-3 py-2 text-right tabular-nums";
const head = "border-b border-border-strong bg-sunken px-3 py-2 text-center text-xs font-medium text-muted";

export function ReportTable({
  rows,
  grandTotal,
  grandReserveTotal,
}: {
  rows: ReportHallRow[];
  grandTotal: number;
  grandReserveTotal: number;
}) {
  const meals = MEAL_ORDER.filter((kind) => rows[0]?.meals.some((m) => m.meal_kind === kind));
  const first = rows[0]?.meals.find((m) => m.meal_kind === meals[0]);
  const types = first?.by_type ?? [];

  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-surface shadow-card">
      <table className="min-w-max border-collapse text-sm">
        <thead>
          <tr>
            <th className={`${head} text-left`} rowSpan={2}>Зал</th>
            {meals.map((kind) => (
              <th key={kind} className={head} colSpan={types.length * 2}>
                {MEAL_LABEL[kind]}
              </th>
            ))}
            <th className={head} colSpan={2}>Итого за день</th>
          </tr>
          <tr>
            {meals.flatMap((kind) =>
              types.flatMap((t) => [
                <th key={`${kind}-${t.meal_type_id}`} className={head}>{t.name}</th>,
                <th key={`${kind}-${t.meal_type_id}-r`} className={head}>Рез. {t.name}</th>,
              ]),
            )}
            <th className={head}>Всего</th>
            <th className={head}>Резерв</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((row) => (
            <tr key={row.hallId}>
              <td className={`${cell} text-left font-medium`}>{row.hallName}</td>
              {meals.flatMap((kind) => {
                const meal = row.meals.find((m) => m.meal_kind === kind);
                return types.flatMap((t) => [
                  <td key={`${kind}-${t.meal_type_id}`} className={cell}>
                    {meal?.by_type.find((x) => x.meal_type_id === t.meal_type_id)?.count ?? 0}
                  </td>,
                  <td key={`${kind}-${t.meal_type_id}-r`} className={cell}>
                    {meal?.reserve_by_type.find((x) => x.meal_type_id === t.meal_type_id)?.count ?? 0}
                  </td>,
                ]);
              })}
              <td className={`${cell} font-medium`}>{row.total}</td>
              <td className={cell}>{row.reserveTotal}</td>
            </tr>
          ))}
        </tbody>

        <tfoot>
          <tr>
            <td className={`${cell} text-left font-semibold`}>ИТОГО</td>
            <td className={`${cell} font-semibold`} colSpan={meals.length * types.length * 2}>
              {grandTotal}
            </td>
            <td className={`${cell} font-semibold`}>{grandTotal}</td>
            <td className={`${cell} font-semibold`}>{grandReserveTotal}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
