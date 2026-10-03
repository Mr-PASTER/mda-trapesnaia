# Трапезная МДА — Frontend, фаза F3: Настройки — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать экран «Настройки»: форма дефолтов (приёмы по умолчанию + тип питания по умолчанию) и отдельный блок выбора темы (Системная / Светлая / Тёмная). Форма дефолтов — общая для питающегося и админа (через `target`).

**Architecture:** Продолжение F1–F2: чистая логика в `lib/`, хуки в `api/`, фичевые компоненты в `features/`. `Target` выносится в `lib/target.ts`, чтобы им пользовались и «Меню», и «Настройки».

**Tech Stack:** те же (React 19, TanStack Query v5, Tailwind v4, Vitest jsdom).

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§7 тема, §9.3 настройки, §10 компоненты)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f2-menu.md`

## Global Constraints

- Дефолты: `GET/PUT /me/defaults` (себя) и `GET/PUT /admin/users/{id}/defaults` (человек).
- Тело PUT дефолтов: `{ default_meal_type_id: string | null, meals: { breakfast, lunch, snack, dinner: boolean } }`.
- Тема: `light | dark | system`, ключ `localStorage["mda.theme"]`, класс `dark` на `<html>` (функции уже есть в `lib/theme.ts`).
- Все тексты — русские; кнопка называется так же, как результат («Сохранить» → тост «Сохранено»).
- Тап-зоны ≥48px; сегменты «Идёт/Не идёт» как в модалке дня.
- Тесты — только юнит-тесты логики.

## Дерево файлов фазы F3

```
syte/src/
  lib/
    target.ts                 # NEW: Target = self | admin
  api/
    me.ts                     # MODIFY: useMyDefaults, useSaveMyDefaults
    admin.ts                  # MODIFY: useUserDefaults, useSaveUserDefaults
  features/
    menu/useMenuData.ts       # MODIFY: импорт Target из lib/target
    defaults/
      useDefaults.ts          # NEW: target-aware хуки дефолтов
      DefaultsForm.tsx        # NEW
    theme/
      ThemeSection.tsx        # NEW
    settings/
      SettingsPage.tsx        # NEW
  app/router.tsx              # MODIFY: /settings -> SettingsPage
syte/tests/
    theme.test.ts             # MODIFY (добавить функцию применения выбора)
```

**Interfaces, которые фаза отдаёт дальше:**
- `lib/target.ts`: `type Target = { mode: "self" } | { mode: "admin"; userId: string }`.
- `features/defaults/useDefaults.ts`: `useDefaults(target)`, `useSaveDefaults(target)`.
- `features/theme/ThemeSection.tsx`: `ThemeSection` (без пропсов).
- `features/settings/SettingsPage.tsx`: `SettingsPage({ target })`.

---

### Task 1: `Target` в `lib` + хуки дефолтов

**Files:**
- Create: `syte/src/lib/target.ts`
- Modify: `syte/src/features/menu/useMenuData.ts`, `syte/src/api/me.ts`, `syte/src/api/admin.ts`

- [ ] **Step 1: Написать `src/lib/target.ts`**

```ts
export type Target = { mode: "self" } | { mode: "admin"; userId: string };
```

- [ ] **Step 2: Обновить `src/features/menu/useMenuData.ts`** — брать `Target` из `lib/target` и реэкспортировать для совместимости:

```ts
import type { Target } from "../../lib/target";

export type { Target };

export function useMenuDays(target: Target, from: string, to: string) {
  const isSelf = target.mode === "self";
  const self = useMyCalendar(from, to, isSelf);
  const admin = useUserCalendar(target.mode === "admin" ? target.userId : "", from, to, !isSelf);
  return isSelf ? self : admin;
}
```
(`useSaveMenuDay` оставить как есть.)

- [ ] **Step 3: Добавить в `src/api/me.ts`**

```ts
export function useMyDefaults(enabled = true) {
  return useQuery({ queryKey: ["defaults", "me"], queryFn: fetchMyDefaults, enabled });
}

export function useSaveMyDefaults() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["DefaultsUpdate"]) => saveMyDefaults(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["defaults"] }),
  });
}
```

- [ ] **Step 4: Добавить в `src/api/admin.ts`**

```ts
export function useUserDefaults(userId: string, enabled = true) {
  return useQuery({
    queryKey: ["defaults", "admin", userId],
    queryFn: () => fetchUserDefaults(userId),
    enabled,
  });
}

export function useSaveUserDefaults(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["DefaultsUpdate"]) => saveUserDefaults(userId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["defaults"] }),
  });
}
```

- [ ] **Step 5: Проверить сборку и тесты**

```bash
cd syte
npm run build
npm run test
```

- [ ] **Step 6: Commit**

```bash
git add syte/src/lib/target.ts syte/src/features/menu/useMenuData.ts syte/src/api/me.ts syte/src/api/admin.ts
git commit -m "feat(front): extract target type and add defaults hooks"
```

---

### Task 2: Блок темы (`ThemeSection.tsx`)

**Files:**
- Create: `syte/src/features/theme/ThemeSection.tsx`
- Modify: `syte/tests/theme.test.ts` (добавить проверку функции применения выбора)

**Interfaces:**
- Consumes: `lib/theme.ts` (`Theme`, `getStoredTheme`, `storeTheme`, `applyTheme`).
- Produces: `ThemeSection`.

- [ ] **Step 1: Дописать падающий тест** в `tests/theme.test.ts`

Проверяем, что выбор темы сохраняется и применяется:

```ts
import { applyTheme, getStoredTheme, storeTheme } from "../src/lib/theme";

describe("theme selection", () => {
  it("persists the choice and toggles the html class", () => {
    document.documentElement.classList.remove("dark");
    storeTheme("dark");
    applyTheme(getStoredTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    storeTheme("light");
    applyTheme(getStoredTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
```

- [ ] **Step 2: Запустить — PASS/FAIL по обстоятельствам.** Если тест уже зелёный (логика есть с F1) — оставить; тест фиксирует поведение.

Run: `cd syte && npm run test`

- [ ] **Step 3: Написать `src/features/theme/ThemeSection.tsx`**

```tsx
import { useState } from "react";
import { applyTheme, getStoredTheme, storeTheme, type Theme } from "../../lib/theme";

const OPTIONS: { value: Theme; label: string }[] = [
  { value: "system", label: "Системная" },
  { value: "light", label: "Светлая" },
  { value: "dark", label: "Тёмная" },
];

export function ThemeSection() {
  const [theme, setTheme] = useState<Theme>(() => getStoredTheme());

  function choose(next: Theme) {
    storeTheme(next);
    applyTheme(next);
    setTheme(next);
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-base font-semibold">Тема оформления</h2>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => choose(option.value)}
            aria-pressed={theme === option.value}
            className={`min-h-11 rounded-xl px-4 text-sm ${
              theme === option.value ? "bg-accent text-white" : "border border-border"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Проверить сборку и тесты** (`npm run build`, `npm run test`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/features/theme syte/tests/theme.test.ts
git commit -m "feat(front): add theme section"
```

---

### Task 3: Форма дефолтов и страница настроек

**Files:**
- Create: `syte/src/features/defaults/useDefaults.ts`, `syte/src/features/defaults/DefaultsForm.tsx`, `syte/src/features/settings/SettingsPage.tsx`
- Modify: `syte/src/app/router.tsx` (`/settings` → `SettingsPage`)

**Interfaces:**
- Consumes: `useMealTypes`, `Target`, хуки дефолтов, `useToast`, UI-кит.
- Produces: `useDefaults(target)`, `useSaveDefaults(target)`, `DefaultsForm({ target })`, `SettingsPage({ target })`.

- [ ] **Step 1: Написать `src/features/defaults/useDefaults.ts`**

```ts
import { useMyDefaults, useSaveMyDefaults } from "../../api/me";
import { useSaveUserDefaults, useUserDefaults } from "../../api/admin";
import type { Target } from "../../lib/target";

export function useDefaults(target: Target) {
  const isSelf = target.mode === "self";
  const self = useMyDefaults(isSelf);
  const admin = useUserDefaults(target.mode === "admin" ? target.userId : "", !isSelf);
  return isSelf ? self : admin;
}

export function useSaveDefaults(target: Target) {
  const self = useSaveMyDefaults();
  const admin = useSaveUserDefaults(target.mode === "admin" ? target.userId : "");
  return isSelf ? self : admin;
}
```

- [ ] **Step 2: Написать `src/features/defaults/DefaultsForm.tsx`**

Требования: загрузка `Spinner`; сегменты типа по `useMealTypes()`; 4 строки приёмов «Идёт/Не идёт» в `MEAL_ORDER`; кнопка **«Сохранить»**; тост «Сохранено» при успехе и «Не удалось сохранить» при ошибке; локальное состояние из загруженных дефолтов (обновлять при получении данных).

```tsx
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
    breakfast: false, lunch: false, snack: false, dinner: false,
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

  if (isLoading) return <Spinner />;

  async function submit() {
    try {
      await save.mutateAsync({ default_meal_type_id: mealTypeId, meals });
      toast("Сохранено");
    } catch {
      toast("Не удалось сохранить");
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-base font-semibold">Мои приёмы по умолчанию</h2>

      <p className="mb-2 text-sm text-muted">Тип питания по умолчанию</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {mealTypes.map((t) => (
          <button key={t.id} type="button" onClick={() => setMealTypeId(t.id)}
            aria-pressed={mealTypeId === t.id}
            className={`min-h-11 rounded-xl px-4 text-sm ${mealTypeId === t.id ? "bg-accent text-white" : "border border-border"}`}>
            {t.name}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        {MEAL_ORDER.map((kind) => (
          <div key={kind} className="flex items-center justify-between gap-3">
            <span className="text-sm">{MEAL_LABEL[kind]}</span>
            <div className="flex gap-2">
              <button type="button" onClick={() => setMeals((m) => ({ ...m, [kind]: true }))}
                className={`min-h-11 rounded-xl px-4 text-sm ${meals[kind] ? "bg-accent text-white" : "border border-border"}`}>
                Идёт
              </button>
              <button type="button" onClick={() => setMeals((m) => ({ ...m, [kind]: false }))}
                className={`min-h-11 rounded-xl px-4 text-sm ${!meals[kind] ? "bg-not-going text-white" : "border border-border"}`}>
                Не идёт
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex justify-end">
        <Button onClick={submit} disabled={save.isPending}>{save.isPending ? "Сохраняем…" : "Сохранить"}</Button>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Написать `src/features/settings/SettingsPage.tsx`**

```tsx
import { DefaultsForm } from "../defaults/DefaultsForm";
import { ThemeSection } from "../theme/ThemeSection";
import type { Target } from "../../lib/target";

export function SettingsPage({ target }: { target: Target }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">
        {target.mode === "self" ? "Настройки" : "Настройки питающегося"}
      </h1>
      <DefaultsForm target={target} />
      <ThemeSection />
    </div>
  );
}
```

- [ ] **Step 4: Прописать маршрут** в `src/app/router.tsx`: заменить заглушку `/settings` на

```tsx
{ path: "/settings", element: <SettingsPage target={{ mode: "self" }} /> },
```

- [ ] **Step 5: Проверить и снять скриншот-проверку вручную**

```bash
cd syte
npm run test
npm run build
npm run dev
```
Проверить: открыть `/settings`, что подтянулись текущие дефолты, переключение «Идёт/Не идёт» и типа, «Сохранить» → тост; переключение темы меняет оформление и сохраняется после перезагрузки.

- [ ] **Step 6: Commit**

```bash
git add syte/src/features/defaults syte/src/features/settings syte/src/app/router.tsx
git commit -m "feat(front): add defaults form and settings page"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F3):** §9.3 (дефолты + отдельный блок темы) — задачи 2–3; §7 (тема, хранение, системная по умолчанию) — задача 2 (логика уже в F1); §10 (общие компоненты, `target`) — задачи 1, 3.
- **Плейсхолдеров нет:** код и команды приведены.
- **Согласованность:** `Target` (единый в `lib/target.ts`), `useDefaults`/`useSaveDefaults`, `DefaultsForm`, `SettingsPage`, `ThemeSection` — одинаковы во всех задачах.
- **Зависимости волн:** T1 (хуки) ‖ T2 (тема) независимы → T3 (форма+страница) после T1.
- **Риск:** `useDefaults` вызывает два хука, но неактивный гейтится `enabled` — как в F2.

## Следующие фазы

- **F4 Админ:** `PeopleList` + маршруты `/people/:userId` (Меню) и `/people/:userId/settings` (Настройки) через `MenuPage`/`SettingsPage` с `target="admin"`.
- **F5 Отчёты** (таблицы + Excel).
- **F6 Оператор** (разделы).
- **F7 Docker/nginx.**
