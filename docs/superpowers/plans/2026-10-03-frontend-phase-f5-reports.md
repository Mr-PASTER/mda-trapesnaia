# Трапезная МДА — Frontend, фаза F5: Отчёты — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Экраны бухгалтера: отчёт за день и за период (таблица «залы × приёмы» с подколонками типов и резерва) и скачивание Excel.

**Architecture:** `api/reports.ts` (запросы) → `features/reports/ReportTable.tsx` (общий рендер таблицы) → страницы `DailyReportPage` / `PeriodReportPage` с выбором даты/периода и кнопкой Excel.

**Tech Stack:** те же.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§9.6, §5)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f4-admin.md`

## Global Constraints

- Эндпоинты: `GET /accountant/report?date&hall_id`, `GET /accountant/report/period?from&to&hall_id`, и экспорт `.../export` (скачивание файла).
- Колонки зависят от активных типов: из `by_type` (имена) строим подколонки; рядом — `reserve_by_type` («Рез. …»).
- Итоги: по приёму (`total`, `reserve_total`), по залу (`day_total`/`period_total`), и общий (`grand_total`, `grand_reserve_total`).
- Скачивание Excel — обычная ссылка `<a download>` на экспортный эндпоинт (cookie уходит автоматически, same-origin).
- Таблица широкая → обёртка с горизонтальным скроллом на мобильных.
- Монохром + акцент `accent`; тексты русские.

## Дерево файлов фазы F5

```
syte/src/
  api/reports.ts                  # NEW: запросы и хуки
  features/reports/
    ReportTable.tsx               # NEW: общий рендер
    DailyReportPage.tsx           # NEW
    PeriodReportPage.tsx          # NEW
  app/router.tsx                  # MODIFY: /reports/daily, /reports/period
```

---

### Task 1: API отчётов (`api/reports.ts`)

**Files:**
- Create: `syte/src/api/reports.ts`

- [ ] **Step 1: Написать `src/api/reports.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type DailyReport = components["schemas"]["DailyReportOut"];
export type PeriodReport = components["schemas"]["PeriodReportOut"];
export type MealReport = components["schemas"]["MealReportOut"];

function hallQuery(hallId?: string): string {
  return hallId ? `&hall_id=${hallId}` : "";
}

export function fetchDailyReport(date: string, hallId?: string): Promise<DailyReport> {
  return apiFetch<DailyReport>(`/accountant/report?date=${date}${hallQuery(hallId)}`);
}

export function fetchPeriodReport(from: string, to: string, hallId?: string): Promise<PeriodReport> {
  return apiFetch<PeriodReport>(`/accountant/report/period?from=${from}&to=${to}${hallQuery(hallId)}`);
}

export function useDailyReport(date: string, hallId?: string) {
  return useQuery({
    queryKey: ["report", "daily", date, hallId ?? "all"],
    queryFn: () => fetchDailyReport(date, hallId),
  });
}

export function usePeriodReport(from: string, to: string, hallId?: string) {
  return useQuery({
    queryKey: ["report", "period", from, to, hallId ?? "all"],
    queryFn: () => fetchPeriodReport(from, to, hallId),
  });
}

export function dailyExportUrl(date: string, hallId?: string): string {
  return `/api/v1/accountant/report/export?date=${date}${hallQuery(hallId)}`;
}

export function periodExportUrl(from: string, to: string, hallId?: string): string {
  return `/api/v1/accountant/report/period/export?from=${from}&to=${to}${hallQuery(hallId)}`;
}
```

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/api/reports.ts
git commit -m "feat(front): add report api"
```

---

### Task 2: Таблица отчёта (`ReportTable.tsx`)

**Files:**
- Create: `syte/src/features/reports/ReportTable.tsx`

**Interfaces:**
- Produces: `ReportTable({ rows, grandTotal, grandReserveTotal })`, тип `ReportHallRow`.

- [ ] **Step 1: Написать `ReportTable.tsx`**

```tsx
import { MEAL_LABEL, MEAL_ORDER } from "../../lib/mealKind";
import type { MealReport } from "../../api/reports";

export type ReportHallRow = {
  hallId: string;
  hallName: string;
  meals: MealReport[];
  total: number;
  reserveTotal: number;
};

const cell = "border-b border-border px-3 py-2 text-right tabular-nums";
const head = "border-b border-border bg-paper px-3 py-2 text-center text-xs font-medium text-muted";

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
    <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
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
```

> Строка «ИТОГО» намеренно простая: слева подпись, затем объединённая ячейка с общим числом и колонки «Всего/Резерв».

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/features/reports/ReportTable.tsx
git commit -m "feat(front): add report table"
```

---

### Task 3: Страницы отчётов и маршруты

**Files:**
- Create: `syte/src/features/reports/DailyReportPage.tsx`, `syte/src/features/reports/PeriodReportPage.tsx`
- Modify: `syte/src/app/router.tsx`

- [ ] **Step 1: Написать `DailyReportPage.tsx`**

Требования: `<input type="date">` (по умолчанию — сегодня); таблица; кнопка-ссылка «Скачать Excel»; загрузка/ошибка/пусто.

```tsx
import { useState } from "react";
import { todayIso } from "../../lib/dates";
import { useDailyReport, dailyExportUrl } from "../../api/reports";
import { ReportTable, type ReportHallRow } from "./ReportTable";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { Input } from "../../components/ui/Input";

export function DailyReportPage() {
  const [date, setDate] = useState(todayIso());
  const { data, isLoading, isError } = useDailyReport(date);

  const rows: ReportHallRow[] = (data?.halls ?? []).map((h) => ({
    hallId: h.hall_id,
    hallName: h.hall_name,
    meals: h.meals,
    total: h.day_total,
    reserveTotal: h.day_reserve_total,
  }));

  return (
    <div className="mx-auto max-w-6xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Отчёт за день</h1>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Дата
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <a
          href={dailyExportUrl(date)}
          className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-sm hover:bg-surface"
          download
        >
          Скачать Excel
        </a>
      </div>

      {isLoading && <Spinner />}
      {isError && <p className="text-sm font-medium text-accent">Не удалось загрузить отчёт</p>}
      {data && rows.length === 0 && <EmptyState title="За выбранный день данных нет" />}
      {rows.length > 0 && (
        <ReportTable rows={rows} grandTotal={data!.grand_total} grandReserveTotal={data!.grand_reserve_total} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Написать `PeriodReportPage.tsx`** по той же схеме: два `input type="date"` (`from`/`to`, по умолчанию — начало текущего месяца и сегодня), `usePeriodReport`, `periodExportUrl`, имена полей `period_total`/`period_reserve_total`.

- [ ] **Step 3: Прописать маршруты** в `app/router.tsx` внутри `RequireRole(["accountant"])`:

```tsx
{ path: "/reports/daily", element: <DailyReportPage /> },
{ path: "/reports/period", element: <PeriodReportPage /> },
```

- [ ] **Step 4: Проверить сборку, тесты и вручную**

```bash
cd syte
npm run test
npm run build
npm run dev
```
Проверить: выбор даты/периода, таблица, «Скачать Excel» скачивает файл.

- [ ] **Step 5: Commit**

```bash
git add syte/src/features/reports syte/src/app/router.tsx
git commit -m "feat(front): add daily and period report pages"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F5):** §9.6 (выбор дня/периода, таблица, Excel) — задачи 1–3; §5 (эндпоинты) — задача 1.
- **Плейсхолдеров нет:** код и команды приведены.
- **Согласованность:** `useDailyReport`, `usePeriodReport`, `dailyExportUrl`, `periodExportUrl`, `ReportTable`, `ReportHallRow` — единообразно.
- **Риск:** в отчёте может не быть активных типов/залов — `ReportTable` должен не падать при пустых `rows`/`types` (использует `?? 0` и `rows[0]?`).

## Следующие фазы

- **F6 Оператор** (разделы: пользователи, залы, типы питания, правила, настройки, логи, календарь).
- **F7 Docker/nginx.**
