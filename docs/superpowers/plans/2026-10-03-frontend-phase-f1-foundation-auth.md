# Трапезная МДА — Frontend, фаза F1: Foundation & Auth — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поднять каркас React SPA: сборка Vite, Tailwind с токенами и темами, типизированный API-клиент с cookie-сессией и отпечатком устройства, layout с сворачиваемым сайдбаром, вход/выход и защищённые маршруты, плюс юнит-тесты логики.

**Architecture:** Слои `lib` (чистая логика) → `api` (сеть) → `app` (провайдеры, роутер, layout) → `features` (экраны) → `components/ui` (кит). Данные — TanStack Query; серверное состояние кэшируется, мутации инвалидируют. Аутентификация — httpOnly cookie (`credentials: "same-origin"`), на клиенте токен не хранится.

**Tech Stack:** Node 24, Vite, React, TypeScript, React Router v7, TanStack Query v5, Tailwind CSS v4, Vitest (jsdom), `openapi-typescript`.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md`

## Global Constraints

- Каталог приложения: `syte/` (пустой на старте).
- Базовый префикс API: `/api/v1`; dev-прокси Vite: `/api` → `http://localhost:8000`.
- Все запросы: `credentials: "same-origin"` + заголовок `X-Device-Fingerprint`.
- На клиенте **не хранится токен**; сессия — httpOnly cookie.
- Тема: `light` | `dark` | `system`, класс `dark` на `<html>`, ключ `localStorage["mda.theme"]`, по умолчанию `system`.
- Отпечаток: `localStorage["mda.device"]` (UUID) → заголовок `sha256(uuid + ":" + navigator.userAgent)` (WebCrypto), результат кэшируется в модуле.
- UI-тексты — русские; действия в повелительном наклонении («Сохранить», «Войти»).
- Тесты — только **юнит-тесты логики** (Vitest, окружение `jsdom`); компонентных/E2E нет.
- Типы API генерируются из OpenAPI в `src/api/schema.d.ts` — руками не редактируются.

## Дерево файлов фазы F1

```
syte/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  scripts/gen-api-types.mjs
  src/
    main.tsx
    styles/index.css             # tailwind + токены + тёмная тема
    lib/
      theme.ts
      storage.ts                 # безопасные обёртки localStorage
    api/
      fingerprint.ts
      client.ts
      auth.ts
      schema.d.ts                # генерируется
    app/
      queryClient.ts
      providers.tsx
      router.tsx
      guards.tsx
      AppLayout.tsx
      Sidebar.tsx
    components/ui/
      Button.tsx  Input.tsx  Card.tsx  Spinner.tsx  EmptyState.tsx  Toast.tsx
    features/auth/LoginPage.tsx
  tests/
    theme.test.ts
    fingerprint.test.ts
    client.test.ts
```

**Interfaces, которые фаза отдаёт дальше:**
- `lib/theme.ts`: `Theme = "light"|"dark"|"system"`, `getStoredTheme()`, `setTheme(t)`, `resolveTheme(t, prefersDark)`, `applyTheme(t)`, `subscribeSystemTheme(cb)`.
- `api/fingerprint.ts`: `getDeviceFingerprint(): Promise<string>` (hex sha256), `resetDeviceId(): void`.
- `api/client.ts`: `apiFetch<T>(path, init?)`, `ApiError`, `ConflictError`, `setUnauthorizedHandler(fn)`.
- `api/auth.ts`: `login(login, password)`, `logout()`, `fetchMe()`, типы `Me`, `MealType`.
- `app/guards.tsx`: `RequireAuth`, `RequireRole`.

---

### Task 1: Скаффолд Vite + Tailwind + Vitest

**Files:**
- Create: `syte/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/styles/index.css`
- Test: `syte/tests/smoke.test.ts`

- [ ] **Step 1: Создать проект**

```bash
cd syte
npm create vite@latest . -- --template react-ts
npm install
npm install react-router
npm install @tanstack/react-query
npm install -D tailwindcss @tailwindcss/vite vitest jsdom @types/node
npm install -D openapi-typescript
```

> Если `npm create vite` в непустом/текущем каталоге спросит подтверждение — согласиться с перезаписью только служебных файлов (каталог пуст).

- [ ] **Step 2: `vite.config.ts` — react + tailwind + прокси + vitest**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.ts"],
  },
});
```

- [ ] **Step 3: `src/styles/index.css` — Tailwind v4, токены, тёмная тема**

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

:root {
  --paper: #f7f8f6;
  --surface: #ffffff;
  --ink: #1e2a24;
  --muted: #67766d;
  --accent: #2f6b4e;
  --not-going: #b0463c;
  --lock: #7c7466;
  --absent: #c2703a;
  --border: #e3e7e2;
}

.dark {
  --paper: #141816;
  --surface: #1d2320;
  --ink: #e8ede9;
  --muted: #93a29a;
  --accent: #5fa57e;
  --not-going: #d9786f;
  --lock: #8a8378;
  --absent: #d98a55;
  --border: #2a322d;
}

@theme inline {
  --color-paper: var(--paper);
  --color-surface: var(--surface);
  --color-ink: var(--ink);
  --color-muted: var(--muted);
  --color-accent: var(--accent);
  --color-not-going: var(--not-going);
  --color-lock: var(--lock);
  --color-absent: var(--absent);
  --color-border: var(--border);
  --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

html, body, #root { height: 100%; }
body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 4: `index.html` — базовый HTML**

```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>Трапезная МДА</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: `src/main.tsx` — точка входа (пока минимальная)**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className="p-6 text-ink">Трапезная МДА</div>
  </StrictMode>,
);
```

- [ ] **Step 6: `tests/smoke.test.ts` — падающий/проходящий тест окружения**

```ts
import { describe, expect, it } from "vitest";

describe("test runner", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 7: Скрипты в `package.json`**

Добавить:
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "gen:api": "node scripts/gen-api-types.mjs"
  }
}
```

- [ ] **Step 8: Прогнать**

```bash
cd syte
npm run test
npm run build
```
Expected: тест зелёный, сборка без ошибок.

- [ ] **Step 9: Commit**

```bash
git add syte
git commit -m "chore(front): scaffold Vite React app with Tailwind and Vitest"
```

---

### Task 2: Тема (`lib/theme.ts`)

**Files:**
- Create: `syte/src/lib/storage.ts`, `syte/src/lib/theme.ts`
- Test: `syte/tests/theme.test.ts`

**Interfaces:**
- Produces: `type Theme = "light" | "dark" | "system"`, `getStoredTheme()`, `storeTheme(t)`, `resolveTheme(t, prefersDark)`, `applyTheme(t)`, `subscribeSystemTheme(cb)`.

- [ ] **Step 1: Написать `src/lib/storage.ts`**

```ts
export function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* приватный режим/квота — игнорируем */
  }
}
```

- [ ] **Step 2: Написать падающий тест `tests/theme.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { resolveTheme, STORAGE_KEY } from "../src/lib/theme";
import { getStoredTheme, storeTheme } from "../src/lib/theme";

describe("resolveTheme", () => {
  it("returns explicit themes as-is", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
  it("resolves system from prefers-color-scheme", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
});

describe("stored theme", () => {
  it("defaults to system and round-trips", () => {
    window.localStorage.clear();
    expect(getStoredTheme()).toBe("system");
    storeTheme("dark");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("dark");
    expect(getStoredTheme()).toBe("dark");
  });
});
```

- [ ] **Step 3: Запустить — FAIL**, затем написать `src/lib/theme.ts`**

```ts
import { readLocal, writeLocal } from "./storage";

export type Theme = "light" | "dark" | "system";
export const STORAGE_KEY = "mda.theme";

export function getStoredTheme(): Theme {
  const raw = readLocal(STORAGE_KEY);
  return raw === "light" || raw === "dark" || raw === "system" ? raw : "system";
}

export function storeTheme(theme: Theme): void {
  writeLocal(STORAGE_KEY, theme);
}

export function resolveTheme(theme: Theme, prefersDark: boolean): "light" | "dark" {
  if (theme === "system") return prefersDark ? "dark" : "light";
  return theme;
}

export function applyTheme(theme: Theme): void {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolved = resolveTheme(theme, prefersDark);
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

export function subscribeSystemTheme(cb: () => void): () => void {
  const mql = window.matchMedia("(prefers-color-scheme: dark)");
  mql.addEventListener("change", cb);
  return () => mql.removeEventListener("change", cb);
}
```

- [ ] **Step 4: Прогнать — PASS** (`npm run test`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/lib syte/tests/theme.test.ts
git commit -m "feat(front): add theme resolution and storage"
```

---

### Task 3: Отпечаток устройства (`api/fingerprint.ts`)

**Files:**
- Create: `syte/src/api/fingerprint.ts`
- Test: `syte/tests/fingerprint.test.ts`

**Interfaces:**
- Produces: `getDeviceFingerprint(): Promise<string>`, `resetDeviceId(): void`.

- [ ] **Step 1: Написать падающий тест `tests/fingerprint.test.ts`**

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { getDeviceFingerprint, resetDeviceId } from "../src/api/fingerprint";

describe("device fingerprint", () => {
  beforeEach(() => resetDeviceId());

  it("is a stable 64-char hex string", async () => {
    const a = await getDeviceFingerprint();
    const b = await getDeviceFingerprint();
    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(a).toBe(b);
  });

  it("is stored on the device", async () => {
    await getDeviceFingerprint();
    expect(window.localStorage.getItem("mda.device")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Запустить — FAIL**, затем написать `src/api/fingerprint.ts`**

```ts
import { readLocal, writeLocal } from "../lib/storage";

const DEVICE_KEY = "mda.device";
let cached: string | null = null;

async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function deviceId(): string {
  let id = readLocal(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    writeLocal(DEVICE_KEY, id);
  }
  return id;
}

export async function getDeviceFingerprint(): Promise<string> {
  if (cached) return cached;
  cached = await sha256Hex(`${deviceId()}:${navigator.userAgent}`);
  return cached;
}

export function resetDeviceId(): void {
  cached = null;
  try {
    window.localStorage.removeItem(DEVICE_KEY);
  } catch {
    /* ignore */
  }
}
```

- [ ] **Step 3: Прогнать — PASS.**

> Если `crypto.subtle` недоступен в jsdom-окружении — добавить в тест `Object.defineProperty(globalThis, "crypto", { value: webcrypto })` из `node:crypto`.

- [ ] **Step 4: Commit**

```bash
git add syte/src/api/fingerprint.ts syte/tests/fingerprint.test.ts
git commit -m "feat(front): add device fingerprint"
```

---

### Task 4: API-клиент (`api/client.ts`)

**Files:**
- Create: `syte/src/api/client.ts`
- Test: `syte/tests/client.test.ts`

**Interfaces:**
- Produces: `ApiError`, `ConflictError`, `apiFetch<T>(path, init?)`, `setUnauthorizedHandler(fn)`.

- [ ] **Step 1: Написать падающий тест `tests/client.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError, ConflictError, setUnauthorizedHandler } from "../src/api/client";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("sends fingerprint header and parses json", async () => {
    const fetchMock = mockFetch(200, { ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const res = await apiFetch<{ ok: boolean }>("/catalog/meal-types");
    expect(res.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/v1/catalog/meal-types");
    expect((init.headers as Record<string, string>)["X-Device-Fingerprint"]).toMatch(/^[0-9a-f]{64}$/);
    expect(init.credentials).toBe("same-origin");
  });

  it("calls unauthorized handler on 401", async () => {
    vi.stubGlobal("fetch", mockFetch(401, { detail: "invalid_session" }));
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    await expect(apiFetch("/me")).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalled();
  });

  it("throws ConflictError with current payload on 409", async () => {
    vi.stubGlobal("fetch", mockFetch(409, { detail: "record_changed", current: { date: "2026-10-03" } }));
    await expect(apiFetch("/me/days/2026-10-03", { method: "PUT" })).rejects.toBeInstanceOf(ConflictError);
  });
});
```

- [ ] **Step 2: Запустить — FAIL**, затем написать `src/api/client.ts`**

```ts
import { getDeviceFingerprint } from "./fingerprint";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export class ConflictError extends ApiError {
  current: unknown;
  constructor(detail: unknown, current: unknown) {
    super(409, detail);
    this.current = current;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const fingerprint = await getDeviceFingerprint();
  const headers = new Headers(init.headers);
  headers.set("X-Device-Fingerprint", fingerprint);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });

  if (response.status === 401) {
    onUnauthorized?.();
    throw new ApiError(401, "unauthorized");
  }

  let payload: unknown = undefined;
  if (response.status !== 204) {
    const text = await response.text();
    payload = text ? JSON.parse(text) : undefined;
  }

  if (!response.ok) {
    const detail = (payload as { detail?: unknown })?.detail ?? `HTTP ${response.status}`;
    if (response.status === 409) {
      throw new ConflictError(detail, (payload as { current?: unknown })?.current);
    }
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}
```

- [ ] **Step 3: Прогнать — PASS.**

- [ ] **Step 4: Commit**

```bash
git add syte/src/api/client.ts syte/tests/client.test.ts
git commit -m "feat(front): add api client with fingerprint and error handling"
```

---

### Task 5: Генерация типов API

**Files:**
- Create: `syte/scripts/gen-api-types.mjs`
- Create (generated): `syte/src/api/schema.d.ts`

- [ ] **Step 1: Написать `scripts/gen-api-types.mjs`**

```js
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";

const source = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json";
execSync(`npx openapi-typescript ${source} -o src/api/schema.d.ts`, { stdio: "inherit" });
console.log("Generated src/api/schema.d.ts");
```

- [ ] **Step 2: Запустить при живом бэкенде**

```bash
cd syte
npm run gen:api
```
Expected: создан `src/api/schema.d.ts` (бэкенд поднят на :8000).

- [ ] **Step 3: Добавить алиасы в `src/api/auth.ts`** (см. Task 6).

- [ ] **Step 4: Commit**

```bash
git add syte/scripts syte/src/api/schema.d.ts syte/package.json
git commit -m "chore(front): generate api types from openapi"
```

---

### Task 6: Аутентификация и запросы (`api/auth.ts`, `app/queryClient.ts`)

**Files:**
- Create: `syte/src/api/auth.ts`, `syte/src/app/queryClient.ts`

**Interfaces:**
- Consumes: `apiFetch`.
- Produces: `login(login, password)`, `logout()`, `fetchMe()`, `useCurrentUser()`, `queryClient`.

- [ ] **Step 1: Написать `src/app/queryClient.ts`**

```ts
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 30_000, refetchOnWindowFocus: false },
  },
});
```

- [ ] **Step 2: Написать `src/api/auth.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { components } from "./schema";

export type Me = components["schemas"]["MeOut"];
export type MealType = components["schemas"]["MealTypeOut"];

export function login(login: string, password: string): Promise<Me> {
  return apiFetch<Me>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login, password }),
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function fetchMe(): Promise<Me> {
  return apiFetch<Me>("/auth/me");
}

export function useCurrentUser() {
  return useQuery({ queryKey: ["me"], queryFn: fetchMe, retry: false });
}
```

> Имена схем (`MeOut`, `MealTypeOut`) должны совпасть с тем, что сгенерировано в `schema.d.ts`; при расхождении поправить имена здесь.

- [ ] **Step 3: Commit**

```bash
git add syte/src/api/auth.ts syte/src/app/queryClient.ts
git commit -m "feat(front): add auth api and query client"
```

---

### Task 7: Провайдеры, роутер, гварды

**Files:**
- Create: `syte/src/app/providers.tsx`, `syte/src/app/guards.tsx`, `syte/src/app/router.tsx`
- Modify: `syte/src/main.tsx`

**Interfaces:**
- Consumes: `queryClient`, `useCurrentUser`, `setUnauthorizedHandler`, `applyTheme`.
- Produces: `RequireAuth`, `RequireRole`, `App` (роутер).

- [ ] **Step 1: Написать `src/app/providers.tsx`**

```tsx
import { useEffect, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./queryClient";
import { applyTheme, getStoredTheme, subscribeSystemTheme, type Theme } from "../lib/theme";
import { setUnauthorizedHandler } from "../api/client";

export function AppProviders({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    setUnauthorizedHandler(() => {
      window.location.assign("/login?reason=expired");
    });
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

> Тема применяется в `ThemeSection` (фаза F3) и при старте — добавь `useEffect(() => applyTheme(getStoredTheme()), [])` и подписку `subscribeSystemTheme` в отдельном `ThemeInitializer` внутри провайдеров.

- [ ] **Step 2: Написать `src/app/guards.tsx`**

```tsx
import { Navigate, Outlet, useLocation } from "react-router";
import { useCurrentUser } from "../api/auth";

const HOME_BY_ROLE: Record<string, string> = {
  eater: "/menu",
  admin: "/people",
  operator: "/operator/users",
  accountant: "/reports/daily",
};

export function RequireAuth() {
  const { data, isLoading, isError } = useCurrentUser();
  const location = useLocation();
  if (isLoading) return <div className="p-6 text-muted">Загрузка…</div>;
  if (isError || !data) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function RequireRole({ roles }: { roles: string[] }) {
  const { data } = useCurrentUser();
  if (data && !roles.includes(data.role)) return <Navigate to={HOME_BY_ROLE[data.role] ?? "/login"} replace />;
  return <Outlet />;
}
```

- [ ] **Step 3: Написать `src/app/router.tsx`**

```tsx
import { createBrowserRouter, Navigate } from "react-router";
import { RequireAuth, RequireRole } from "./guards";
import { AppLayout } from "./AppLayout";
import { LoginPage } from "../features/auth/LoginPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/menu", element: <div className="p-6">Меню (F2)</div> },
          { path: "/settings", element: <div className="p-6">Настройки (F3)</div> },
          {
            element: <RequireRole roles={["admin"]} />,
            children: [{ path: "/people", element: <div className="p-6">Люди (F4)</div> }],
          },
          {
            element: <RequireRole roles={["accountant"]} />,
            children: [{ path: "/reports/daily", element: <div className="p-6">Отчёт (F5)</div> }],
          },
          {
            element: <RequireRole roles={["operator"]} />,
            children: [{ path: "/operator/users", element: <div className="p-6">Пользователи (F6)</div> }],
          },
          { path: "/", element: <Navigate to="/menu" replace /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
```

- [ ] **Step 4: Обновить `src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import "./styles/index.css";
import { AppProviders } from "./app/providers";
import { router } from "./app/router";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
);
```

- [ ] **Step 5: Проверить сборку**

```bash
cd syte
npm run build
```
Expected: сборка без ошибок типов.

- [ ] **Step 6: Commit**

```bash
git add syte/src/app syte/src/main.tsx
git commit -m "feat(front): add providers, router and role guards"
```

---

### Task 8: UI-кит (базовые компоненты)

**Files:**
- Create: `syte/src/components/ui/Button.tsx`, `Input.tsx`, `Card.tsx`, `Spinner.tsx`, `EmptyState.tsx`, `Toast.tsx`

- [ ] **Step 1: Написать `Button.tsx`**

```tsx
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const base =
    "inline-flex items-center justify-center rounded-xl px-4 min-h-11 text-sm font-medium transition disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-white hover:brightness-95",
    ghost: "bg-transparent text-ink border border-border hover:bg-surface",
    danger: "bg-not-going text-white hover:brightness-95",
  };
  return <button className={`${base} ${styles[variant]} ${className}`} {...props} />;
}
```

- [ ] **Step 2: Написать `Input.tsx`, `Card.tsx`, `Spinner.tsx`, `EmptyState.tsx`**

```tsx
// Input.tsx
import type { InputHTMLAttributes } from "react";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`}
      {...props}
    />
  );
}
```

```tsx
// Card.tsx
export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`rounded-2xl border border-border bg-surface p-4 ${className}`}>{children}</div>;
}
```

```tsx
// Spinner.tsx
export function Spinner() {
  return <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-accent" role="status" aria-label="Загрузка" />;
}
```

```tsx
// EmptyState.tsx
export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border p-8 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}
```

- [ ] **Step 3: Написать `Toast.tsx`** — простой контекст:

```tsx
import { createContext, useCallback, useContext, useState } from "react";

type Toast = { id: number; text: string };
const ToastContext = createContext<(text: string) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string) => {
    const id = Date.now();
    setItems((prev) => [...prev, { id, text }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2">
        {items.map((t) => (
          <div key={t.id} className="rounded-xl bg-ink px-4 py-2 text-sm text-paper shadow-lg">
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
```

> Оберни приложение в `ToastProvider` внутри `AppProviders`.

- [ ] **Step 4: Проверить сборку** (`npm run build`).

- [ ] **Step 5: Commit**

```bash
git add syte/src/components syte/src/app/providers.tsx
git commit -m "feat(front): add base ui kit"
```

---

### Task 9: Layout с сайдбаром

**Files:**
- Create: `syte/src/app/AppLayout.tsx`, `syte/src/app/Sidebar.tsx`

**Interfaces:**
- Consumes: `useCurrentUser`, `logout`, `lib/storage`.
- Produces: `AppLayout`.

- [ ] **Step 1: Написать `src/app/Sidebar.tsx`**

Требования: пункты меню зависят от роли; **на мобильном свёрнут по умолчанию**, состояние хранится в `localStorage["mda.sidebar"]`; сворачивание кнопкой; внизу — кнопка «Выйти».

```tsx
import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router";
import { logout, useCurrentUser } from "../api/auth";
import { queryClient } from "./queryClient";
import { readLocal, writeLocal } from "../lib/storage";

type Item = { to: string; label: string };

const NAV: Record<string, Item[]> = {
  eater: [
    { to: "/menu", label: "Моё меню" },
    { to: "/settings", label: "Настройки" },
  ],
  admin: [
    { to: "/people", label: "Питающиеся" },
    { to: "/settings", label: "Настройки" },
  ],
  operator: [
    { to: "/operator/users", label: "Пользователи" },
    { to: "/operator/halls", label: "Залы" },
    { to: "/operator/meal-types", label: "Типы питания" },
    { to: "/operator/rules", label: "Правила" },
    { to: "/operator/settings", label: "Настройки" },
    { to: "/operator/logs", label: "Логи" },
    { to: "/operator/calendar", label: "Календарь" },
  ],
  accountant: [
    { to: "/reports/daily", label: "Отчёт за день" },
    { to: "/reports/period", label: "Отчёт за период" },
  ],
};

export function Sidebar() {
  const { data: me } = useCurrentUser();
  const navigate = useNavigate();
  const [open, setOpen] = useState<boolean>(() => readLocal("mda.sidebar") === "open");

  useEffect(() => {
    writeLocal("mda.sidebar", open ? "open" : "closed");
  }, [open]);

  if (!me) return null;
  const items = NAV[me.role] ?? [];

  async function handleLogout() {
    try {
      await logout();
    } finally {
      queryClient.clear();
      navigate("/login", { replace: true });
    }
  }

  return (
    <aside className={`flex shrink-0 flex-col border-r border-border bg-surface transition-all ${open ? "w-56" : "w-14"}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="m-2 min-h-10 rounded-xl text-sm text-muted hover:bg-paper"
        aria-label={open ? "Свернуть меню" : "Развернуть меню"}
      >
        {open ? "«" : "»"}
      </button>
      <nav className="flex flex-1 flex-col gap-1 px-2">
        {items.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            className={({ isActive }) =>
              `rounded-xl px-3 py-2 text-sm ${isActive ? "bg-accent text-white" : "text-ink hover:bg-paper"}`
            }
          >
            {open ? i.label : i.label.slice(0, 1)}
          </NavLink>
        ))}
      </nav>
      <button onClick={handleLogout} className="m-2 rounded-xl px-3 py-2 text-sm text-muted hover:bg-paper">
        {open ? "Выйти" : "⎋"}
      </button>
    </aside>
  );
}
```

> Пункты меню, экраны которых появятся позже (F3–F6), ведут на заглушки — это ок для F1.

- [ ] **Step 2: Написать `src/app/AppLayout.tsx`**

```tsx
import { Outlet } from "react-router";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Проверить сборку** (`npm run build`).

- [ ] **Step 4: Commit**

```bash
git add syte/src/app/AppLayout.tsx syte/src/app/Sidebar.tsx
git commit -m "feat(front): add app layout with collapsible sidebar"
```

---

### Task 10: Экран входа

**Files:**
- Create: `syte/src/features/auth/LoginPage.tsx`

- [ ] **Step 1: Написать `LoginPage.tsx`**

```tsx
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { login, useCurrentUser } from "../../api/auth";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { queryClient } from "../../app/queryClient";

export function LoginPage() {
  const [params] = useSearchParams();
  const expired = params.get("reason") === "expired";
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useCurrentUser(); // прогреваем (не мешает вводу)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(loginValue, password);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Неверный логин или пароль" : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <h1 className="mb-4 text-xl font-semibold">Трапезная МДА</h1>
        {expired && <p className="mb-3 rounded-lg bg-paper px-3 py-2 text-xs text-muted">Сессия истекла — войдите заново</p>}
        <form className="flex flex-col gap-3" onSubmit={onSubmit}>
          <label className="text-sm">
            Логин
            <Input value={loginValue} onChange={(e) => setLoginValue(e.target.value)} autoComplete="username" required />
          </label>
          <label className="text-sm">
            Пароль
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          {error && <p className="text-sm text-not-going">{error}</p>}
          <Button type="submit" disabled={busy}>{busy ? "Входим…" : "Войти"}</Button>
        </form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Прогнать тесты и сборку**

```bash
cd syte
npm run test
npm run build
```

- [ ] **Step 3: Ручная проверка (сквозная)**

```bash
# в одном терминале — бэкенд
cd server && docker compose up -d db && uv run uvicorn app.main:app --port 8000
# в другом — фронт
cd syte && npm run dev
```
Открыть `http://localhost:5173`, войти созданным оператором (`demo_op`/`secret123`), проверить: сайдбар свёрнут на узком экране, пункты по роли, «Выйти» возвращает на `/login`.

- [ ] **Step 4: Commit**

```bash
git add syte/src/features/auth
git commit -m "feat(front): add login page"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F1):** §3 стек, §4 структура, §5 API-слой, §6 сессия/отпечаток, §7 тема, §8 токены (цвет/типографика), §9.1 экран входа, §12 адаптив (свёрнутый сайдбар), §14 юнит-тесты — покрыто задачами 1–10.
- **Плейсхолдеров нет:** код и команды приведены; заглушки маршрутов `(F2)…(F6)` помечены как временные.
- **Согласованность имён:** `apiFetch`, `ApiError`, `ConflictError`, `getDeviceFingerprint`, `resolveTheme`, `applyTheme`, `useCurrentUser`, `RequireAuth`, `RequireRole`, `AppLayout`, `Sidebar` — одинаковы во всех задачах.
- **Риски:** в тестах jsdom может не быть `crypto.subtle` — в Task 3 дан явный обходной путь; имена схем (`MeOut`, `MealTypeOut`) зависят от генерации — Task 6 содержит пометку.

## Следующие фазы

- **F2 Меню:** `useCalendar`, `DayGrid`, `DayCard`, `DayEditModal`, `lib/dates.ts`, `lib/dayStatus.ts` (+ юнит-тесты).
- **F3 Настройки:** `DefaultsForm`, `ThemeSection`.
- **F4 Админ:** `PeopleList` + режим «за человека» (`/people/:userId`).
- **F5 Отчёты:** таблицы + скачивание Excel.
- **F6 Оператор:** разделы.
- **F7 Docker/nginx + README.**
