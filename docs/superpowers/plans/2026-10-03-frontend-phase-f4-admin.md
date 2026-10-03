# Трапезная МДА — Frontend, фаза F4: Админ — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать администратору список питающихся его залов (с клиентским поиском) и вход в **те же** экраны, что видит питающийся, но за конкретного человека.

**Architecture:** Переиспользуем `MenuPage` и `SettingsPage` с `target = { mode: "admin", userId }`. Список — новый feature `features/people`. Навигация «← К списку» + переключение «Меню / Настройки» внутри страницы человека.

**Tech Stack:** те же.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§9.2, §9.3, §9.4)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f3-settings.md`

## Global Constraints

- Данные списка — `GET /admin/users` через `usePeople()` (`api/admin.ts`); сервер при `hall_id` без параметра отдаёт питающихся залов админа.
- Поиск — **чисто клиентский** (по `full_name` и `login`, регистронезависимо).
- Имена залов берём из `useCurrentUser().halls` (`MeOut.halls`), сопоставляя `hall_ids`.
- Все маршруты человека — под `RequireRole(["admin"])`.
- Тап-зоны ≥48px; монохром + акцент `accent`.

## Дерево файлов фазы F4

```
syte/src/
  features/people/
    PeoplePage.tsx            # NEW: список + поиск
    PersonRoutes.tsx          # NEW: обёртки, читающие :userId из URL
  features/menu/MenuPage.tsx       # MODIFY: ссылка «Настройки» для админа
  features/settings/SettingsPage.tsx  # MODIFY: ссылка «Меню» для админа
  app/router.tsx              # MODIFY: /people, /people/:userId, /people/:userId/settings
```

---

### Task 1: Список питающихся (`PeoplePage.tsx`)

**Files:**
- Create: `syte/src/features/people/PeoplePage.tsx`

- [ ] **Step 1: Написать `PeoplePage.tsx`**

Требования: заголовок «Питающиеся»; поле поиска; список строк (ФИО + залы); тап/клик по строке → `/people/:userId`; состояния загрузки/ошибки/пустоты.

```tsx
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { usePeople } from "../../api/admin";
import { useCurrentUser } from "../../api/auth";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";

export function PeoplePage() {
  const navigate = useNavigate();
  const { data: me } = useCurrentUser();
  const { data: people, isLoading, isError } = usePeople();
  const [query, setQuery] = useState("");

  const hallName = useMemo(() => {
    const map = new Map<string, string>();
    (me?.halls ?? []).forEach((h) => map.set(h.id, h.name));
    return map;
  }, [me]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = people ?? [];
    if (!q) return list;
    return list.filter(
      (p) => p.full_name.toLowerCase().includes(q) || p.login.toLowerCase().includes(q),
    );
  }, [people, query]);

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Питающиеся</h1>

      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск по имени или логину"
        aria-label="Поиск"
      />

      {isLoading && <div className="mt-4"><Spinner /></div>}
      {isError && <p className="mt-4 text-sm font-medium text-accent">Не удалось загрузить список</p>}

      {!isLoading && !isError && filtered.length === 0 && (
        <div className="mt-4">
          <EmptyState
            title={query ? "Никого не найдено" : "В ваших залах пока нет питающихся"}
            hint={query ? "Попробуйте изменить запрос" : undefined}
          />
        </div>
      )}

      <ul className="mt-4 flex flex-col gap-2">
        {filtered.map((person) => (
          <li key={person.id}>
            <button
              type="button"
              onClick={() => navigate(`/people/${person.id}`)}
              className="flex min-h-12 w-full flex-col items-start rounded-2xl border border-border bg-surface px-4 py-3 text-left hover:border-accent/60"
            >
              <span className="text-sm font-medium">{person.full_name}</span>
              <span className="text-xs text-muted">
                {person.login}
                {person.hall_ids.length > 0 &&
                  ` · ${person.hall_ids.map((id) => hallName.get(id) ?? "Зал").join(", ")}`}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Проверить сборку** (`npm run build`).

- [ ] **Step 3: Commit**

```bash
git add syte/src/features/people
git commit -m "feat(front): add people list page"
```

---

### Task 2: Маршруты человека и переключение «Меню / Настройки»

**Files:**
- Create: `syte/src/features/people/PersonRoutes.tsx`
- Modify: `syte/src/features/menu/MenuPage.tsx`, `syte/src/features/settings/SettingsPage.tsx`, `syte/src/app/router.tsx`

- [ ] **Step 1: Написать `PersonRoutes.tsx`**

```tsx
import { useParams } from "react-router";
import { MenuPage } from "../menu/MenuPage";
import { SettingsPage } from "../settings/SettingsPage";

export function PersonMenuPage() {
  const { userId = "" } = useParams();
  return <MenuPage target={{ mode: "admin", userId }} />;
}

export function PersonSettingsPage() {
  const { userId = "" } = useParams();
  return <SettingsPage target={{ mode: "admin", userId }} />;
}
```

- [ ] **Step 2: В `MenuPage.tsx`** для админа добавить рядом с «← К списку» ссылку на настройки человека:

```tsx
<Link to={`/people/${target.mode === "admin" ? target.userId : ""}/settings`}
      className="min-h-11 rounded-xl border border-border px-3 text-sm leading-[2.75rem]">
  Настройки
</Link>
```
(импортировать `Link` из `react-router`; показывать только при `target.mode === "admin"`).

- [ ] **Step 3: В `SettingsPage.tsx`** для админа добавить ссылку «Меню» (`/people/:userId`) и «← К списку» (`/people`).

- [ ] **Step 4: Прописать маршруты** в `app/router.tsx` внутри ветки `RequireRole(["admin"])`:

```tsx
{ path: "/people", element: <PeoplePage /> },
{ path: "/people/:userId", element: <PersonMenuPage /> },
{ path: "/people/:userId/settings", element: <PersonSettingsPage /> },
```

- [ ] **Step 5: Проверить сборку, тесты и вручную**

```bash
cd syte
npm run test
npm run build
npm run dev
```
Проверить: список людей, поиск, переход в меню человека, переключение на «Настройки», «← К списку».

- [ ] **Step 6: Commit**

```bash
git add syte/src/features/people syte/src/features/menu/MenuPage.tsx syte/src/features/settings/SettingsPage.tsx syte/src/app/router.tsx
git commit -m "feat(front): add admin person routes and menu/settings switch"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F4):** §9.4 (список + поиск) — Task 1; §9.2/§9.3 (те же экраны за человека, возврат к списку) — Task 2.
- **Плейсхолдеров нет:** код и команды приведены.
- **Согласованность:** `usePeople`, `PeoplePage`, `PersonMenuPage`, `PersonSettingsPage`, `target="admin"` — единообразно.
- **Риск:** для демонстрации нужен админ с залом и питающиеся — в dev-БД их может не быть; при проверке вручную сначала создать оператором зал, админа и питающегося.

## Следующие фазы

- **F5 Отчёты** (таблицы + скачивание Excel).
- **F6 Оператор** (разделы).
- **F7 Docker/nginx.**
