# Трапезная МДА — Frontend, фаза F6a: Справочники оператора — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разделы оператора «Пользователи», «Залы», «Типы питания»: списки-таблицы и формы создания/редактирования, плюс недостающие UI-примитивы.

**Architecture:** `api/operator.ts` (запросы и хуки) → UI-примитивы (`Table`, `Select`, `Badge`) → страницы разделов. Маршруты `/operator/*` прописываются в конце одной задачей, чтобы не конфликтовать по файлу роутера.

**Tech Stack:** те же.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§9.5)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f5-reports.md`

## Global Constraints

- Эндпоинты оператора (все требуют роль `operator`): `/operator/halls`, `/operator/meal-types`, `/operator/users`, `/operator/users/{id}/halls`, `/operator/users/{id}/password`.
- Ошибки: `409 already_exists`/`login_exists`, `400 invalid_halls`/`invalid_meal_type`/`last_meal_type`, `404 *_not_found`. Показываем понятный текст на русском через тост.
- Удаление пользователя: по умолчанию **мягкое** (`DELETE`, `hard=false`); жёсткое — `hard=true` с подтверждением.
- Типы питания: нельзя деактивировать последний активный (сервер вернёт `400 last_meal_type`).
- Монохром + акцент `accent`; текст на `bg-accent` — `text-on-accent` (никогда `text-white`). Тап-зоны ≥48px.
- Только русский; действия в повелительном наклонении.

## Дерево файлов фазы F6a

```
syte/src/
  api/operator.ts                 # NEW
  components/ui/
    Table.tsx                     # NEW: тонкая обёртка таблицы
    Select.tsx                    # NEW
    Badge.tsx                     # NEW
  features/operator/
    HallsPage.tsx                 # NEW
    MealTypesPage.tsx             # NEW
    UsersPage.tsx                 # NEW
  app/router.tsx                  # MODIFY (в Task 5)
```

**Interfaces, которые фаза отдаёт дальше:**
- `api/operator.ts`: `useHalls`, `useCreateHall`, `useUpdateHall`, `useDeleteHall`, `useMealTypesAll`, `useCreateMealType`, `useUpdateMealType`, `useDeleteMealType`, `useOperatorUsers`, `useCreateUser`, `useUpdateUser`, `useSetUserHalls`, `useSetUserPassword`, `useDeleteUser`.
- UI: `Table`, `Select`, `Badge`.

---

### Task 1: API оператора (`api/operator.ts`)

**Files:**
- Create: `syte/src/api/operator.ts`

- [ ] **Step 1: Написать `src/api/operator.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type Hall = components["schemas"]["HallOut"];
export type MealTypeRow = components["schemas"]["MealTypeOut"];
export type OperatorUser = components["schemas"]["OperatorUserOut"];

// --- Залы ---
export const useHalls = (onlyActive = false) =>
  useQuery({
    queryKey: ["op", "halls", onlyActive],
    queryFn: () => apiFetch<Hall[]>(`/operator/halls?only_active=${onlyActive}`),
  });

export const useCreateHall = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => apiFetch<Hall>("/operator/halls", { method: "POST", body: JSON.stringify({ name }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "halls"] }),
  });
};

export const useUpdateHall = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiFetch<Hall>(`/operator/halls/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "halls"] }),
  });
};

export const useDeleteHall = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/operator/halls/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "halls"] }),
  });
};

// --- Типы питания ---
export const useMealTypesAll = () =>
  useQuery({
    queryKey: ["op", "meal-types"],
    queryFn: () => apiFetch<MealTypeRow[]>("/operator/meal-types?only_active=false"),
  });

export const useCreateMealType = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; sort_order: number; icon: string | null }) =>
      apiFetch<MealTypeRow>("/operator/meal-types", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["op", "meal-types"] });
      qc.invalidateQueries({ queryKey: ["meal-types"] });
    },
  });
};

export const useUpdateMealType = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<MealTypeRow>(`/operator/meal-types/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["op", "meal-types"] });
      qc.invalidateQueries({ queryKey: ["meal-types"] });
    },
  });
};

export const useDeleteMealType = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/operator/meal-types/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "meal-types"] }),
  });
};

// --- Пользователи ---
export const useOperatorUsers = () =>
  useQuery({
    queryKey: ["op", "users"],
    queryFn: () => apiFetch<OperatorUser[]>("/operator/users?only_active=false"),
  });

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<OperatorUser>("/operator/users", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};

export const useUpdateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<OperatorUser>(`/operator/users/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};

export const useSetUserHalls = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, hallIds }: { id: string; hallIds: string[] }) =>
      apiFetch<OperatorUser>(`/operator/users/${id}/halls`, { method: "PUT", body: JSON.stringify({ hall_ids: hallIds }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};

export const useSetUserPassword = () =>
  useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      apiFetch<void>(`/operator/users/${id}/password`, { method: "PUT", body: JSON.stringify({ password }) }),
  });

export const useDeleteUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, hard }: { id: string; hard: boolean }) =>
      apiFetch<void>(`/operator/users/${id}?hard=${hard}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "users"] }),
  });
};
```

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/api/operator.ts
git commit -m "feat(front): add operator api"
```

---

### Task 2: UI-примитивы (`Table`, `Select`, `Badge`)

**Files:**
- Create: `syte/src/components/ui/Table.tsx`, `Select.tsx`, `Badge.tsx`

- [ ] **Step 1: Написать `Table.tsx`**

```tsx
export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return (
    <th className={`border-b border-border bg-paper px-3 py-2 text-left text-xs font-medium text-muted ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`border-b border-border px-3 py-2 align-middle ${className}`}>{children}</td>;
}
```

- [ ] **Step 2: Написать `Select.tsx`**

```tsx
import type { SelectHTMLAttributes } from "react";

export function Select({ className = "", children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}
```

- [ ] **Step 3: Написать `Badge.tsx`**

```tsx
export function Badge({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "accent" }) {
  const styles = tone === "accent" ? "bg-accent text-on-accent" : "bg-paper text-muted border border-border";
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${styles}`}>{children}</span>;
}
```

- [ ] **Step 4: Проверить сборку** (`npm run build`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/components/ui
git commit -m "feat(front): add table, select and badge primitives"
```

---

### Task 3: Страницы «Залы» и «Типы питания»

**Files:**
- Create: `syte/src/features/operator/HallsPage.tsx`, `syte/src/features/operator/MealTypesPage.tsx`

- [ ] **Step 1: Написать `HallsPage.tsx`**

Требования: таблица (название, активность, действия); форма создания (инпут + «Добавить»); переименование (инлайн-модалка или поле); деактивация с подтверждением; тосты на `409`/ошибки.

```tsx
import { useState } from "react";
import { Table, Td, Th } from "../../components/ui/Table";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Spinner } from "../../components/ui/Spinner";
import { useToast } from "../../components/ui/Toast";
import { useCreateHall, useDeleteHall, useHalls, useUpdateHall } from "../../api/operator";
import { ApiError } from "../../api/client";

export function HallsPage() {
  const toast = useToast();
  const { data, isLoading } = useHalls();
  const create = useCreateHall();
  const update = useUpdateHall();
  const remove = useDeleteHall();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);

  function report(err: unknown) {
    if (err instanceof ApiError && err.status === 409) toast("Зал с таким названием уже есть");
    else if (err instanceof ApiError && err.status === 400) toast("Нельзя: операция запрещена");
    else toast("Не удалось выполнить");
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Залы</h1>

      <div className="mb-4 flex gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название зала" />
        <Button
          onClick={async () => {
            try {
              await create.mutateAsync(name.trim());
              setName("");
              toast("Зал добавлен");
            } catch (err) {
              report(err);
            }
          }}
          disabled={!name.trim() || create.isPending}
        >
          Добавить
        </Button>
      </div>

      {isLoading && <Spinner />}
      {data && (
        <Table>
          <thead>
            <tr>
              <Th>Название</Th>
              <Th>Статус</Th>
              <Th className="text-right">Действия</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((hall) => (
              <tr key={hall.id}>
                <Td>
                  {editing?.id === hall.id ? (
                    <Input value={editing.name} onChange={(e) => setEditing({ id: hall.id, name: e.target.value })} />
                  ) : (
                    hall.name
                  )}
                </Td>
                <Td>{hall.is_active ? <Badge>активен</Badge> : <Badge tone="accent">выключен</Badge>}</Td>
                <Td className="text-right">
                  {editing?.id === hall.id ? (
                    <Button
                      variant="ghost"
                      onClick={async () => {
                        try {
                          await update.mutateAsync({ id: hall.id, name: editing.name.trim() });
                          setEditing(null);
                          toast("Сохранено");
                        } catch (err) {
                          report(err);
                        }
                      }}
                    >
                      Сохранить
                    </Button>
                  ) : (
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing({ id: hall.id, name: hall.name })}>
                        Переименовать
                      </Button>
                      {hall.is_active && (
                        <Button
                          variant="danger"
                          onClick={async () => {
                            try {
                              await remove.mutateAsync(hall.id);
                              toast("Зал выключен");
                            } catch (err) {
                              report(err);
                            }
                          }}
                        >
                          Выключить
                        </Button>
                      )}
                    </div>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Написать `MealTypesPage.tsx`**

Аналогично залам, плюс поле **иконки** (`Select` со значениями: `meat`, `lent`, `fish`, «без иконки»), `sort_order` (число) и предупреждение на `400 last_meal_type` («Нельзя выключить последний тип питания»).

- [ ] **Step 3: Проверить сборку** (`npm run build`).

- [ ] **Step 4: Commit**

```bash
git add syte/src/features/operator
git commit -m "feat(front): add halls and meal types pages"
```

---

### Task 4: Страница «Пользователи»

**Files:**
- Create: `syte/src/features/operator/UsersPage.tsx`

- [ ] **Step 1: Написать `UsersPage.tsx`**

Требования:
- Таблица: логин, ФИО, роль (Badge), залы, активность, действия.
- Кнопка «Добавить пользователя» → модалка создания: `login`, `password`, `full_name`, `role` (Select: eater/admin/accountant/operator), `hall_ids` (мультивыбор из `useHalls()`), `default_meal_type_id` (Select из `useMealTypesAll()`), с подсказкой про правило залов по ролям.
- Редактирование: `full_name`, `role`, `default_meal_type_id`; отдельно — залы (`setHalls`), сброс пароля (`setPassword`).
- Удаление: мягкое + жёсткое (жёсткое — с подтверждением `window.confirm`).
- Ошибки: `409 login_exists` → «Такой логин уже занят»; `400 invalid_halls` → «Для этой роли нужно другое число залов»; `400 invalid_meal_type` → «Выберите активный тип питания».

(Использовать `Modal`, `Select`, `Table`, `Badge`, тосты; мультивыбор залов — чекбоксами в модалке.)

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/features/operator/UsersPage.tsx
git commit -m "feat(front): add operator users page"
```

---

### Task 5: Маршруты оператора

**Files:**
- Modify: `syte/src/app/router.tsx`

- [ ] **Step 1: Прописать маршруты** внутри `RequireRole(["operator"])`:

```tsx
{ path: "/operator/users", element: <UsersPage /> },
{ path: "/operator/halls", element: <HallsPage /> },
{ path: "/operator/meal-types", element: <MealTypesPage /> },
```
Остальные пункты сайдбара оператора (`/operator/rules`, `/operator/settings`, `/operator/logs`, `/operator/calendar`) оставить заглушками — их закрывает фаза F6b.

- [ ] **Step 2: Проверить сборку, тесты и вручную**

```bash
cd syte
npm run test
npm run build
npm run dev
```
Проверить: создать зал, создать тип питания с иконкой, создать питающегося с залом, отредактировать, сменить пароль, удалить.

- [ ] **Step 3: Commit**

```bash
git add syte/src/app/router.tsx
git commit -m "feat(front): wire operator reference routes"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F6a):** §9.5 (пользователи, залы, типы питания) — задачи 1, 3, 4; §10 (UI-кит: таблица, селект, бейдж) — задача 2; маршруты — задача 5.
- **Плейсхолдеров нет:** код и команды приведены; для «Типов питания» и «Пользователей» точные требования и обработка ошибок описаны, код строится по образцу «Залов».
- **Согласованность:** `useHalls`, `useCreateHall`, `useUpdateHall`, `useDeleteHall`, `useMealTypesAll`, `useOperatorUsers`, `useCreateUser`, `useSetUserHalls`, `useSetUserPassword`, `useDeleteUser`, `Table/Th/Td`, `Select`, `Badge` — единообразно.
- **Риск:** правила залов по ролям (eater — ровно 1; admin — ≥1; accountant/operator — 0) — подсказать в форме и понятно показать `400 invalid_halls`.

## Следующие фазы

- **F6b:** Правила расписания, Настройки, Логи, Календарь (перегенерация).
- **F7 Docker/nginx.**
