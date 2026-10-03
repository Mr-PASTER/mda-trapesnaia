# Трапезная МДА — Frontend, фаза F8: доступ оператора ко всем панелям — план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Привести UI в соответствие с исходным ТЗ — «оператор имеет доступ ко всем панелям»: открыть оператору разделы администратора (питающиеся) и бухгалтера (отчёты), сделать их доступными из сайдбара, при этом **не давать** править отметки (это осознанное ограничение из спеки).

**Architecture:** Только фронтенд. Бэкенд уже разрешает доступ: `/admin/*` под `require_roles(admin, operator)`, `/accountant/*` под `require_roles(accountant, operator)`. Меняются гварды маршрутов, состав сайдбара и добавляется режим «только просмотр».

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§2, §9.5)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f7-docker.md`

## Global Constraints

- Оператор **не редактирует отметки и дефолты питающихся** (сервер вернёт `403`) — в UI это «только просмотр».
- Иконки навигации — **монохромные** (инлайн-SVG), без эмодзи.
- Маршруты `/people*` — `RequireRole(["admin","operator"])`; `/reports/*` — `RequireRole(["accountant","operator"])`.

## Files

- `syte/src/components/ui/Icon.tsx` — NEW: одноцветные иконки навигации.
- `syte/src/app/Sidebar.tsx` — эмодзи → `Icon`; оператору добавлены «Питающиеся», «Отчёт за день», «Отчёт за период», «Моё меню»; «Настройки» оператора переименованы в «Настройки системы».
- `syte/src/app/router.tsx` — гварды `/people*` и `/reports/*` включают оператора.
- `syte/src/features/menu/MenuPage.tsx` — проп `readOnly`: не открывает модалку, показывает «Только просмотр».
- `syte/src/features/settings/SettingsPage.tsx` — проп `readOnly`: вместо формы дефолтов — пометка о просмотре.
- `syte/src/features/people/PersonRoutes.tsx` — `readOnly` для оператора (`useCurrentUser().role === "operator"`).

## Steps

- [x] Создать `Icon` с набором монохромных иконок.
- [x] Обновить сайдбар: иконки SVG, состав пунктов оператора.
- [x] Расширить гварды маршрутов `/people*` и `/reports/*`.
- [x] Добавить `readOnly` в `MenuPage` и `SettingsPage`, прокинуть из `PersonRoutes` для оператора.
- [x] Проверка: `npm run test` (20), `npm run build`; сквозной прогон оператором — `/admin/users` 200, отчёты 200, чтение календаря 200, правка 403.
- [x] Пересобрать контейнер `frontend`.

## Self-Review

- **Покрытие:** доступ оператора к панелям админа и бухгалтера — гварды + сайдбар; запрет правок — `readOnly` + серверный `403`.
- **Риск:** оператор видит «Моё меню», но у него нет зала — плитки будут без «подаётся»; это ожидаемо и не мешает.

## Следующие шаги (не запланированы)

Визуальная полировка, E2E-тесты (Playwright), прод-хардненинг (HTTPS, `SESSION_COOKIE_SECURE=true`, бэкапы, CI).
