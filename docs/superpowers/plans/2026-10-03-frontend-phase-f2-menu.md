# Трапезная МДА — Frontend, фаза F2: Меню — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать ядро приложения — сетку плиток-дней и модалку редактирования дня (тип питания + «иду/не иду» по 4 приёмам), общей для питающегося и администратора.

**Architecture:** Чистая логика (`lib/dates`, `lib/dayStatus`, `lib/mealKind`) → API-функции и хуки (`api/catalog`, `api/me`, `api/admin`) → компоненты (`features/menu/*`). Компоненты не знают, «за кого» работают: страница выбирает эндпоинты через `target` и передаёт вниз данные и обработчики.

**Tech Stack:** те же (React 19, react-router v8, TanStack Query v5, Tailwind v4, Vitest jsdom).

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§8–§11)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f1-foundation-auth.md`

## Global Constraints

- Типы — из `src/api/schema.d.ts` (`DayStateOut`, `MealStateOut`, `MealTypeOut`, `MealKind`, `DayUpdateRequest`, `DefaultsOut`).
- Все запросы — через `apiFetch` (cookie + отпечаток; `401` и `409` уже обрабатываются клиентом).
- Лента — от **сегодня** вперёд, диапазон запроса `from = сегодня`, `to = сегодня + 30` (сервер ограничивает 90 днями).
- Дни с `available = false` рисуем **рыжими** («дня нет») и не открываем на редактирование.
- Заблокированный день (`editable = false`) — палочки в цвете `lock` + глиф замка; модалка не открывается (тост «Приём закрыт»).
- Приёмы с `is_served = false` — «не подаётся», выбор недоступен.
- **Размеры (увеличены):** плитка — квадрат ~`104px` (моб.) / `120–132px` (ПК); «палочка» `5×20px` со скруглением; тап-зоны ≥`48px`.
- Версия дня (`version`) уходит в `PUT`; при `409` берём `current` из ошибки и **подменяем** состояние формы, показываем тост.
- Тесты — только юнит-тесты логики (Vitest).

## Дерево файлов фазы F2

```
syte/src/
  lib/
    dates.ts          # форматирование (рус.)
    mealKind.ts       # порядок и подписи приёмов
    dayStatus.ts      # статусы плитки и гнезда
  api/
    catalog.ts        # useMealTypes
    me.ts             # календарь и сохранение дня (self)
    admin.ts          # календарь и сохранение дня человека (admin)
  components/ui/
    MealTypeIcon.tsx  # inline-SVG по ключу icon (meat/lent/fish + запасная)
  features/menu/
    useMenuData.ts    # target-aware хуки (self | admin)
    DayCard.tsx
    DayGrid.tsx
    DayEditModal.tsx
    MenuPage.tsx
syte/tests/
    dates.test.ts
    dayStatus.test.ts
```

**Interfaces, которые фаза отдаёт дальше:**
- `lib/dates.ts`: `todayIso()`, `iso(Date)`, `parseIso(string)`, `addDays(iso, n)`, `rangeIso(from, to)`, `formatDayShort(iso)`, `formatWeekdayShort(iso)`, `formatDayFull(iso)`.
- `lib/mealKind.ts`: `MealKind`, `MEAL_ORDER`, `MEAL_LABEL`.
- `lib/dayStatus.ts`: `tileStatus(day)`, `mealStatus(item)`, типы `TileStatus`, `MealStatus`.
- `features/menu/useMenuData.ts`: `Target`, `useMenuDays(target, from, to)`, `useSaveMenuDay(target)`.

---

### Task 1: Русские даты и приёмы (`lib/dates.ts`, `lib/mealKind.ts`)

**Files:**
- Create: `syte/src/lib/dates.ts`, `syte/src/lib/mealKind.ts`
- Test: `syte/tests/dates.test.ts`

- [ ] **Step 1: Написать `src/lib/mealKind.ts`**

```ts
import type { components } from "../api/schema";

export type MealKind = components["schemas"]["MealKind"];

export const MEAL_ORDER: MealKind[] = ["breakfast", "lunch", "snack", "dinner"];

export const MEAL_LABEL: Record<MealKind, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  snack: "Полдник",
  dinner: "Ужин",
};
```

- [ ] **Step 2: Написать падающий тест `tests/dates.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import {
  addDays,
  formatDayFull,
  formatDayShort,
  formatWeekdayShort,
  iso,
  parseIso,
  rangeIso,
} from "../src/lib/dates";

describe("dates", () => {
  it("round-trips iso without timezone shifts", () => {
    expect(iso(parseIso("2026-10-03"))).toBe("2026-10-03");
  });

  it("formats the short date in Russian", () => {
    expect(formatDayShort("2026-10-03")).toBe("3 октября");
    expect(formatDayShort("2026-05-01")).toBe("1 мая");
  });

  it("formats weekday short", () => {
    expect(formatWeekdayShort("2026-10-03")).toBe("Сб");
  });

  it("formats the full date with weekday", () => {
    expect(formatDayFull("2026-10-12")).toBe("Понедельник, 12 октября 2026");
  });

  it("adds days and builds a range", () => {
    expect(addDays("2026-10-03", 2)).toBe("2026-10-05");
    expect(rangeIso("2026-10-03", "2026-10-06")).toEqual([
      "2026-10-03",
      "2026-10-04",
      "2026-10-05",
      "2026-10-06",
    ]);
    expect(rangeIso("2026-10-03", "2026-10-02")).toEqual([]);
  });
});
```

- [ ] **Step 3: Запустить — FAIL**, затем написать `src/lib/dates.ts`**

```ts
const WEEKDAYS_FULL = [
  "Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота",
];
const WEEKDAYS_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];
const MONTHS_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

export function parseIso(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function iso(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function todayIso(): string {
  return iso(new Date());
}

export function addDays(value: string, days: number): string {
  const date = parseIso(value);
  date.setDate(date.getDate() + days);
  return iso(date);
}

export function rangeIso(from: string, to: string): string[] {
  const result: string[] = [];
  let current = from;
  while (current <= to) {
    result.push(current);
    current = addDays(current, 1);
  }
  return result;
}

export function formatDayShort(value: string): string {
  const date = parseIso(value);
  return `${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]}`;
}

export function formatWeekdayShort(value: string): string {
  return WEEKDAYS_SHORT[parseIso(value).getDay()];
}

export function formatDayFull(value: string): string {
  const date = parseIso(value);
  return `${WEEKDAYS_FULL[date.getDay()]}, ${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]} ${date.getFullYear()}`;
}
```

- [ ] **Step 4: Прогнать — PASS** (`npm run test`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/lib/dates.ts syte/src/lib/mealKind.ts syte/tests/dates.test.ts
git commit -m "feat(front): add russian date and meal kind helpers"
```

---

### Task 2: Статусы плитки и гнезда (`lib/dayStatus.ts`)

**Files:**
- Create: `syte/src/lib/dayStatus.ts`
- Test: `syte/tests/dayStatus.test.ts`

- [ ] **Step 1: Написать падающий тест `tests/dayStatus.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { mealStatus, tileStatus } from "../src/lib/dayStatus";

describe("tileStatus", () => {
  it("marks non-generated days as absent", () => {
    expect(tileStatus({ available: false, editable: false })).toBe("absent");
    expect(tileStatus({ available: false, editable: true })).toBe("absent");
  });
  it("marks days past the deadline as locked", () => {
    expect(tileStatus({ available: true, editable: false })).toBe("locked");
  });
  it("marks editable days", () => {
    expect(tileStatus({ available: true, editable: true })).toBe("editable");
  });
});

describe("mealStatus", () => {
  it("handles not served", () => {
    expect(mealStatus({ is_served: false, is_going: true })).toBe("not_served");
  });
  it("handles going and not going", () => {
    expect(mealStatus({ is_served: true, is_going: true })).toBe("going");
    expect(mealStatus({ is_served: true, is_going: false })).toBe("not_going");
  });
});
```

- [ ] **Step 2: Запустить — FAIL**, затем написать `src/lib/dayStatus.ts`**

```ts
import type { components } from "../api/schema";

type DayLike = Pick<components["schemas"]["DayStateOut"], "available" | "editable">;
type ItemLike = Pick<components["schemas"]["MealStateOut"], "is_served" | "is_going">;

export type TileStatus = "absent" | "locked" | "editable";
export type MealStatus = "going" | "not_going" | "not_served";

export function tileStatus(day: DayLike): TileStatus {
  if (!day.available) return "absent";
  return day.editable ? "editable" : "locked";
}

export function mealStatus(item: ItemLike): MealStatus {
  if (!item.is_served) return "not_served";
  return item.is_going ? "going" : "not_going";
}
```

- [ ] **Step 3: Прогнать — PASS.**

- [ ] **Step 4: Commit**

```bash
git add syte/src/lib/dayStatus.ts syte/tests/dayStatus.test.ts
git commit -m "feat(front): add tile and meal status helpers"
```

---

### Task 3: API-функции и хуки (`api/catalog.ts`, `api/me.ts`, `api/admin.ts`)

**Files:**
- Create: `syte/src/api/catalog.ts`, `syte/src/api/me.ts`, `syte/src/api/admin.ts`

**Interfaces:**
- Produces: `useMealTypes()`, `useMenuDaysRaw`, `saveMyDay`, `saveUserDay`, типы `DayState`, `DayUpdate`.

- [ ] **Step 1: Написать `src/api/catalog.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { MealType } from "./auth";

export function fetchMealTypes(): Promise<MealType[]> {
  return apiFetch<MealType[]>("/catalog/meal-types");
}

export function useMealTypes() {
  return useQuery({
    queryKey: ["meal-types"],
    queryFn: fetchMealTypes,
    staleTime: 5 * 60_000,
  });
}
```

- [ ] **Step 2: Написать `src/api/me.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type DayState = components["schemas"]["DayStateOut"];
export type DayUpdate = components["schemas"]["DayUpdateRequest"];
export type Defaults = components["schemas"]["DefaultsOut"];

export function fetchMyCalendar(from: string, to: string): Promise<DayState[]> {
  return apiFetch<DayState[]>(`/me/calendar?from=${from}&to=${to}`);
}

export function saveMyDay(date: string, body: DayUpdate): Promise<DayState> {
  return apiFetch<DayState>(`/me/days/${date}`, { method: "PUT", body: JSON.stringify(body) });
}

export function fetchMyDefaults(): Promise<Defaults> {
  return apiFetch<Defaults>("/me/defaults");
}

export function saveMyDefaults(body: components["schemas"]["DefaultsUpdate"]): Promise<Defaults> {
  return apiFetch<Defaults>("/me/defaults", { method: "PUT", body: JSON.stringify(body) });
}

export function useMyCalendar(from: string, to: string) {
  return useQuery({ queryKey: ["calendar", "me", from, to], queryFn: () => fetchMyCalendar(from, to) });
}

export function useSaveMyDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, body }: { date: string; body: DayUpdate }) => saveMyDay(date, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calendar"] }),
  });
}
```

- [ ] **Step 3: Написать `src/api/admin.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { DayState, DayUpdate, Defaults } from "./me";
import type { components } from "./schema";

export type AdminUser = components["schemas"]["AdminUserOut"];

export function fetchPeople(hallId?: string): Promise<AdminUser[]> {
  const query = hallId ? `?hall_id=${hallId}` : "";
  return apiFetch<AdminUser[]>(`/admin/users${query}`);
}

export function fetchUserCalendar(userId: string, from: string, to: string): Promise<DayState[]> {
  return apiFetch<DayState[]>(`/admin/users/${userId}/calendar?from=${from}&to=${to}`);
}

export function saveUserDay(userId: string, date: string, body: DayUpdate): Promise<DayState> {
  return apiFetch<DayState>(`/admin/requests/${userId}/${date}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function fetchUserDefaults(userId: string): Promise<Defaults> {
  return apiFetch<Defaults>(`/admin/users/${userId}/defaults`);
}

export function saveUserDefaults(
  userId: string,
  body: components["schemas"]["DefaultsUpdate"],
): Promise<Defaults> {
  return apiFetch<Defaults>(`/admin/users/${userId}/defaults`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function usePeople(hallId?: string) {
  return useQuery({ queryKey: ["people", hallId ?? "all"], queryFn: () => fetchPeople(hallId) });
}

export function useUserCalendar(userId: string, from: string, to: string) {
  return useQuery({
    queryKey: ["calendar", "admin", userId, from, to],
    queryFn: () => fetchUserCalendar(userId, from, to),
  });
}

export function useSaveUserDay(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, body }: { date: string; body: DayUpdate }) => saveUserDay(userId, date, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calendar"] }),
  });
}
```

- [ ] **Step 4: Проверить сборку** (`npm run build`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/api/catalog.ts syte/src/api/me.ts syte/src/api/admin.ts
git commit -m "feat(front): add menu api functions and hooks"
```

---

### Task 4: Иконка типа и плитка дня (`MealTypeIcon.tsx`, `DayCard.tsx`, `DayGrid.tsx`)

**Files:**
- Create: `syte/src/components/ui/MealTypeIcon.tsx`, `syte/src/features/menu/DayCard.tsx`, `syte/src/features/menu/DayGrid.tsx`

**Interfaces:**
- Produces: `MealTypeIcon({ icon, className })`, `DayCard({ day, onOpen })`, `DayGrid({ days, onOpen })`.

- [ ] **Step 1: Написать `src/components/ui/MealTypeIcon.tsx`** (inline SVG по ключу)

```tsx
const ICONS: Record<string, string> = {
  // простые силуэты; ключи задаёт оператор в meal_types.icon
  meat: "M12 3c2 3 3 5 3 7a3 3 0 1 1-6 0c0-2 1-4 3-7Z",
  fish: "M4 12c3-4 9-5 14-3-2 4-6 6-10 5l-2 3-1-3-1-2Z",
  lent: "M12 3v18M5 8c3-2 11-2 14 0M6 13c2-1 10-1 12 0",
};

export function MealTypeIcon({ icon, className = "" }: { icon: string | null; className?: string }) {
  if (!icon) return null;
  const path = ICONS[icon];
  if (!path) {
    return (
      <span className={`inline-block rounded-full bg-muted/40 ${className}`} aria-hidden />
    );
  }
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={path} />
    </svg>
  );
}
```

- [ ] **Step 2: Написать `src/features/menu/DayCard.tsx`**

Требования: квадратная плитка (aspect-square), день недели + дата, 4 «палочки», штамп типа, состояния `absent` / `locked` / `editable`.

```tsx
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
```

- [ ] **Step 3: Написать `src/features/menu/DayGrid.tsx`**

```tsx
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
```

- [ ] **Step 4: Проверить сборку** (`npm run build`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/components/ui/MealTypeIcon.tsx syte/src/features/menu/DayCard.tsx syte/src/features/menu/DayGrid.tsx
git commit -m "feat(front): add meal type icon, day card and day grid"
```

---

### Task 5: Модалка дня (`DayEditModal.tsx`)

**Files:**
- Create: `syte/src/features/menu/DayEditModal.tsx`

**Interfaces:**
- Consumes: `Modal` (UI-кит), `Segmented`-подобные кнопки, `useToast`, `ConflictError`.
- Produces: `DayEditModal({ day, mealTypes, onClose, onSave })`.

- [ ] **Step 1: Реализовать `DayEditModal.tsx`**

Требования:
- Заголовок `formatDayFull(day.date)`.
- Блок выбора типа: сегменты по `mealTypes` (текст, без иконок).
- Строки приёмов в порядке `MEAL_ORDER`: подпись + сегмент «Идёт / Не идёт»; если `is_served = false` — подпись «не подаётся» и сегмент задизейблен.
- Кнопки «Отмена» / «Сохранить».
- `Сохранить` отправляет `{ meal_type_id, meals: {…все 4…}, version }` через переданный `onSave`.
- При `ConflictError` — тост «Данные изменил администратор — обновляем значения» и **подстановка** `err.current` в состояние формы (включая новый `version`).
- При `ApiError` 403 — тост «День закрыт для правок», закрытие модалки.

Скелет (дополнить стилями по токенам):

```tsx
import { useState } from "react";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/Toast";
import { ApiError, ConflictError } from "../../api/client";
import { formatDayFull } from "../../lib/dates";
import { MEAL_LABEL, MEAL_ORDER, type MealKind } from "../../lib/mealKind";
import type { DayState, DayUpdate } from "../../api/me";
import type { MealType } from "../../api/auth";

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
  const [going, setGoing] = useState<Record<MealKind, boolean>>(() =>
    Object.fromEntries(
      MEAL_ORDER.map((k) => [k, current.items.find((i) => i.meal_kind === k)?.is_going ?? false]),
    ) as Record<MealKind, boolean>,
  );
  const [busy, setBusy] = useState(false);

  function applyState(next: DayState) {
    setCurrent(next);
    setMealTypeId(next.meal_type_id);
    setGoing(
      Object.fromEntries(
        MEAL_ORDER.map((k) => [k, next.items.find((i) => i.meal_kind === k)?.is_going ?? false]),
      ) as Record<MealKind, boolean>,
    );
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
              className={`min-h-11 rounded-xl px-3 text-sm ${mealTypeId === t.id ? "bg-accent text-white" : "border border-border"}`}
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
                  <button type="button" onClick={() => setGoing((g) => ({ ...g, [kind]: true }))}
                    className={`min-h-11 rounded-xl px-4 text-sm ${going[kind] ? "bg-accent text-white" : "border border-border"}`}>
                    Идёт
                  </button>
                  <button type="button" onClick={() => setGoing((g) => ({ ...g, [kind]: false }))}
                    className={`min-h-11 rounded-xl px-4 text-sm ${!going[kind] ? "bg-not-going text-white" : "border border-border"}`}>
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
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button onClick={submit} disabled={busy}>{busy ? "Сохраняем…" : "Сохранить"}</Button>
        </div>
      </div>
    </Modal>
  );
}
```

> Если компонента `Modal` в UI-ките ещё нет — создать его в этой задаче (`components/ui/Modal.tsx`): оверлей, центрированный диалог на ПК и почти на всю ширину снизу на телефоне, закрытие по Esc и клику по фону.

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/features/menu/DayEditModal.tsx syte/src/components/ui/Modal.tsx
git commit -m "feat(front): add day edit modal"
```

---

### Task 6: Страница меню и маршрут (`useMenuData.ts`, `MenuPage.tsx`)

**Files:**
- Create: `syte/src/features/menu/useMenuData.ts`, `syte/src/features/menu/MenuPage.tsx`
- Modify: `syte/src/app/router.tsx` (маршрут `/menu` → `MenuPage`)

**Interfaces:**
- Produces: `Target = { mode: "self" } | { mode: "admin"; userId: string }`, `useMenuDays(target, from, to)`, `useSaveMenuDay(target)`.

- [ ] **Step 1: Написать `src/features/menu/useMenuData.ts`**

```ts
import { useMyCalendar, useSaveMyDay } from "../../api/me";
import { useSaveUserDay, useUserCalendar } from "../../api/admin";

export type Target = { mode: "self" } | { mode: "admin"; userId: string };

export function useMenuDays(target: Target, from: string, to: string) {
  const self = useMyCalendar(from, to);
  const admin = useUserCalendar(target.mode === "admin" ? target.userId : "", from, to);
  return target.mode === "self" ? self : admin;
}

export function useSaveMenuDay(target: Target) {
  const self = useSaveMyDay();
  const admin = useSaveUserDay(target.mode === "admin" ? target.userId : "");
  return target.mode === "self" ? self : admin;
}
```

- [ ] **Step 2: Написать `src/features/menu/MenuPage.tsx`**

Требования:
- Диапазон: `from = todayIso()`, `to = addDays(from, 30)`.
- Заголовок: «Моё меню» (self) или имя человека + кнопка «← К списку» (admin, `navigate("/people")`).
- Загрузка → `Spinner`; ошибка → «Не удалось загрузить календарь»; пусто → `EmptyState` «Календарь ещё не сформирован».
- `DayGrid` + `DayEditModal`.
- Сохранение через `useSaveMenuDay(target).mutateAsync`.
- На узком экране заголовок и кнопка не должны ломать сетку (перенос по строке).

```tsx
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
      {isError && <p className="text-sm text-not-going">Не удалось загрузить календарь</p>}
      {days && days.length === 0 && <EmptyState title="Календарь ещё не сформирован" hint="Дни появятся после генерации расписания" />}
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
```

- [ ] **Step 3: Прописать маршрут в `src/app/router.tsx`**

Заменить заглушку `/menu`:
```tsx
{ path: "/menu", element: <MenuPage target={{ mode: "self" }} /> },
```

- [ ] **Step 4: Прогнать тесты и сборку, затем проверить руками**

```bash
cd syte
npm run test
npm run build
npm run dev
```
Проверить в браузере (`http://localhost:5173`, вход `demo_op`/`secret123`): плитки-дни, «палочки», рыжие «дня нет», открытие модалки, сохранение, повторное сохранение (проверить `409` можно, открыв тот же день в двух вкладках).

- [ ] **Step 5: Commit**

```bash
git add syte/src/features/menu syte/src/app/router.tsx
git commit -m "feat(front): add menu page and route"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F2):** §9.2 (лента от сегодня, рыжие «дня нет», модалка, `409`/`403`) — задачи 4–6; §10 (общие компоненты) — задачи 4–6; §11 (чистая логика) — задачи 1–2; §8 (размеры, палочки, штамп) — задача 4.
- **Плейсхолдеров нет:** код и команды приведены; в Task 5 дан конкретный скелет.
- **Согласованность:** `todayIso`, `addDays`, `formatDayFull`, `tileStatus`, `mealStatus`, `MEAL_ORDER`, `useMenuDays`, `useSaveMenuDay`, `Target` — одинаковы во всех задачах.
- **Зависимости волн:** T1‖T2‖T3 (независимы) → T4‖T5 (компоненты) → T6 (композиция). `Modal` создаётся в T5, если его ещё нет.
- **Известный риск:** `useMenuDays` вызывает оба хука (self и admin) — второй с пустым `userId` при `mode: "self"`. Query с пустым ключом не должен выполняться: добавить `enabled: target.mode === "admin"`/`"self"` внутри (`useQuery(..., { enabled })`), чтобы не бить в API лишний раз.

## Следующие фазы

- **F3 Настройки:** `DefaultsForm`, `ThemeSection`.
- **F4 Админ:** `PeopleList` + маршрут `/people/:userId` (`MenuPage target="admin"`).
- **F5 Отчёты** (таблицы + Excel).
- **F6 Оператор** (разделы).
- **F7 Docker/nginx.**
