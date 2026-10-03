# Трапезная МДА — Frontend, фаза F6b: Правила и служебное — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Оставшиеся разделы оператора: «Правила расписания», «Настройки» (N/K/H), «Логи», «Календарь» (перегенерация).

**Architecture:** добавить хуки в `api/operator.ts`, затем четыре страницы, затем одним шагом прописать маршруты.

**Tech Stack:** те же.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§9.5)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f6a-operator-reference.md`

## Global Constraints

- Эндпоинты: `/operator/schedule-rules` (CRUD), `/operator/settings` (GET/PUT), `/operator/logs`, `/operator/days/regenerate`.
- Правило: `kind` = `recurring` (нужны `weekdays`, пустые `dates`) или `one_off` (нужны `dates`, пустые `weekdays`); непустые `meal_kinds` и `hall_ids`. Ошибка `400 invalid_rule` → понятный тост.
- Настройки: `generation_days ≥ 1`, `deadline_offset_days ≥ 0`, `deadline_time` — строка `HH:MM:SS`.
- Логи: только чтение; фильтры период/пользователь; лимит.
- Монохром + акцент; тап-зоны ≥48px; русские тексты.

## Дерево файлов фазы F6b

```
syte/src/
  api/operator.ts                 # MODIFY: правила, настройки, логи, перегенерация
  features/operator/
    RulesPage.tsx                 # NEW
    SettingsPage.tsx              # NEW
    LogsPage.tsx                  # NEW
    CalendarPage.tsx              # NEW
  app/router.tsx                  # MODIFY (в Task 5)
```

---

### Task 1: Дополнения API (`api/operator.ts`)

**Files:**
- Modify: `syte/src/api/operator.ts`

- [ ] **Step 1: Добавить в конец `src/api/operator.ts`**

```ts
// --- Правила расписания ---
export type ScheduleRule = components["schemas"]["ScheduleRuleOut"];
export type RuleKind = components["schemas"]["RuleKind"];

export const useRules = (onlyActive = false) =>
  useQuery({
    queryKey: ["op", "rules", onlyActive],
    queryFn: () => apiFetch<ScheduleRule[]>(`/operator/schedule-rules?only_active=${onlyActive}`),
  });

export const useCreateRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<ScheduleRule>("/operator/schedule-rules", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "rules"] }),
  });
};

export const useUpdateRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<ScheduleRule>(`/operator/schedule-rules/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "rules"] }),
  });
};

export const useDeleteRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/operator/schedule-rules/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "rules"] }),
  });
};

// --- Настройки ---
export type OperatorSettings = components["schemas"]["SettingsOut"];

export const useOperatorSettings = () =>
  useQuery({
    queryKey: ["op", "settings"],
    queryFn: () => apiFetch<OperatorSettings>("/operator/settings"),
  });

export const useSaveOperatorSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { generation_days: number; deadline_offset_days: number; deadline_time: string }) =>
      apiFetch<OperatorSettings>("/operator/settings", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["op", "settings"] }),
  });
};

// --- Логи ---
export type AuditLog = components["schemas"]["AuditLogOut"];

export const useLogs = (params: { from?: string; to?: string; userId?: string }) =>
  useQuery({
    queryKey: ["op", "logs", params.from ?? "", params.to ?? "", params.userId ?? ""],
    queryFn: () => {
      const q = new URLSearchParams();
      if (params.from) q.set("from", params.from);
      if (params.to) q.set("to", params.to);
      if (params.userId) q.set("user_id", params.userId);
      const suffix = q.toString() ? `?${q}` : "";
      return apiFetch<AuditLog[]>(`/operator/logs${suffix}`);
    },
  });

// --- Календарь ---
export const useRegenerateDays = () =>
  useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) =>
      apiFetch<void>("/operator/days/regenerate", { method: "POST", body: JSON.stringify({ from, to }) }),
  });
```

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/api/operator.ts
git commit -m "feat(front): add operator rules, settings, logs and regenerate hooks"
```

---

### Task 2: Правила расписания (`RulesPage.tsx`)

**Files:**
- Create: `syte/src/features/operator/RulesPage.tsx`

- [ ] **Step 1: Написать `RulesPage.tsx`**

Требования:
- Таблица правил: тип (повторяющееся/одноразовое), «что выключает» (приёмы), дни (дни недели или даты), залы, статус, действия (выключить).
- Модалка создания/редактирования:
  - `kind` — `Select` (`recurring` → «Повторяющееся», `one_off` → «Одноразовое»);
  - приёмы — чекбоксы из `MEAL_ORDER`/`MEAL_LABEL`;
  - залы — чекбоксы из `useHalls()`;
  - для `recurring` — 7 чекбоксов дней недели (`Пн…Вс`, значения 0…6); для `one_off` — список дат с полем «добавить дату» (`input type="date"`).
- Валидация на клиенте: при `recurring` ≥1 день недели и пустые даты; при `one_off` ≥1 дата; ≥1 приём; ≥1 зал. Иначе — тост «Заполните правило полностью».
- Ошибка `400 invalid_rule` → тост «Проверьте правило».

Использовать `Modal`, `Select`, `Table`, `Badge`, `Button`, `Input`, тосты. Код строится по образцу `HallsPage` из F6a.

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/features/operator/RulesPage.tsx
git commit -m "feat(front): add schedule rules page"
```

---

### Task 3: Настройки и Календарь (`SettingsPage.tsx`, `CalendarPage.tsx`)

**Files:**
- Create: `syte/src/features/operator/SettingsPage.tsx`, `syte/src/features/operator/CalendarPage.tsx`

- [ ] **Step 1: Написать `SettingsPage.tsx`**

Поля: `generation_days` (number, ≥1), `deadline_offset_days` (number, ≥0), `deadline_time` (`input type="time"`, отправлять как `HH:MM:00`). Кнопка «Сохранить» → тост «Сохранено». Подсказка под формой: «Правка закрывается за K дней до даты в H:00».

- [ ] **Step 2: Написать `CalendarPage.tsx`**

Два `input type="date"` (`from` по умолчанию сегодня, `to` = сегодня+30) и кнопка **«Перегенерировать»** → `useRegenerateDays()` → тост «Календарь перегенерирован». Показать диапазон и предупреждение «Изменение правил применяется к сгенерированным дням в этом диапазоне».

- [ ] **Step 3: Проверить сборку** (`npm run build`).

- [ ] **Step 4: Commit**

```bash
git add syte/src/features/operator/SettingsPage.tsx syte/src/features/operator/CalendarPage.tsx
git commit -m "feat(front): add operator settings and calendar pages"
```

---

### Task 4: Логи (`LogsPage.tsx`)

**Files:**
- Create: `syte/src/features/operator/LogsPage.tsx`

- [ ] **Step 1: Написать `LogsPage.tsx`**

Требования: фильтры `from`/`to` (`input type="date"`, по умолчанию — сегодня) и «Показать»; таблица: время (`created_at`, форматировать как `ДД.ММ.ГГГГ ЧЧ:ММ`), действие, тип сущности, id сущности, пользователь. Пусто → `EmptyState` «За выбранный период логов нет».

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/features/operator/LogsPage.tsx
git commit -m "feat(front): add operator logs page"
```

---

### Task 5: Маршруты оператора

**Files:**
- Modify: `syte/src/app/router.tsx`

- [ ] **Step 1: Заменить оставшиеся заглушки** внутри `RequireRole(["operator"])`:

```tsx
{ path: "/operator/rules", element: <RulesPage /> },
{ path: "/operator/settings", element: <OperatorSettingsPage /> },
{ path: "/operator/logs", element: <LogsPage /> },
{ path: "/operator/calendar", element: <CalendarPage /> },
```
(импорт страницы настроек оператора — под алиасом `OperatorSettingsPage`, чтобы не путать с `SettingsPage` ролей.)

- [ ] **Step 2: Проверить сборку, тесты и вручную**

```bash
cd syte
npm run test
npm run build
npm run dev
```
Проверить: создать повторяющееся правило («Вс — без завтрака»), увидеть его в таблице; изменить настройки; перегенерировать календарь; открыть логи.

- [ ] **Step 3: Commit**

```bash
git add syte/src/app/router.tsx
git commit -m "feat(front): wire operator rules, settings, logs and calendar routes"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F6b):** §9.5 (правила, настройки, логи, календарь) — задачи 1–5.
- **Плейсхолдеров нет:** код и требования приведены; страницы «Настройки/Календарь/Логи» описаны точно, код строится по образцу F6a.
- **Согласованность:** `useRules`, `useCreateRule`, `useUpdateRule`, `useDeleteRule`, `useOperatorSettings`, `useSaveOperatorSettings`, `useLogs`, `useRegenerateDays` — единообразно.
- **Риск:** правило `one_off` требует хотя бы одну дату, `recurring` — хотя бы один день недели; сервер вернёт `400 invalid_rule` — продублировать клиентской валидацией.

## Следующая фаза

- **F7 Docker/nginx** — сборка статики и раздача через nginx с проксированием `/api`.
