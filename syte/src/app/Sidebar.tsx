import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router";
import { logout, useCurrentUser } from "../api/auth";
import { queryClient } from "./queryClient";
import { readLocal, writeLocal } from "../lib/storage";

type Item = { to: string; label: string; icon: string };

const SIDEBAR_KEY = "mda.sidebar";

const NAV: Record<string, Item[]> = {
  eater: [
    { to: "/menu", label: "Моё меню", icon: "🍽" },
    { to: "/settings", label: "Настройки", icon: "⚙" },
  ],
  admin: [
    { to: "/people", label: "Питающиеся", icon: "👤" },
    { to: "/settings", label: "Настройки", icon: "⚙" },
  ],
  operator: [
    { to: "/operator/users", label: "Пользователи", icon: "👤" },
    { to: "/operator/halls", label: "Залы", icon: "🏛" },
    { to: "/operator/meal-types", label: "Типы питания", icon: "🍲" },
    { to: "/operator/rules", label: "Правила", icon: "📜" },
    { to: "/operator/settings", label: "Настройки", icon: "⚙" },
    { to: "/operator/logs", label: "Логи", icon: "📈" },
    { to: "/operator/calendar", label: "Календарь", icon: "📅" },
  ],
  accountant: [
    { to: "/reports/daily", label: "Отчёт за день", icon: "📄" },
    { to: "/reports/period", label: "Отчёт за период", icon: "📊" },
  ],
};

export function Sidebar() {
  const { data: me } = useCurrentUser();
  const navigate = useNavigate();
  const [open, setOpen] = useState<boolean>(() => readLocal(SIDEBAR_KEY) === "open");

  useEffect(() => {
    writeLocal(SIDEBAR_KEY, open ? "open" : "closed");
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
    <aside
      className={`flex shrink-0 flex-col border-r border-border bg-surface transition-all ${
        open ? "w-56" : "w-14"
      }`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="m-2 flex min-h-11 items-center justify-center rounded-xl text-sm text-muted hover:bg-paper"
        aria-label={open ? "Свернуть меню" : "Развернуть меню"}
      >
        {open ? "«" : "»"}
      </button>
      <nav className="flex flex-1 flex-col gap-1 px-2">
        {items.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            title={i.label}
            className={({ isActive }) =>
              `flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm ${
                open ? "" : "justify-center"
              } ${isActive ? "bg-accent text-white" : "text-ink hover:bg-paper"}`
            }
          >
            <span className="text-lg leading-none" aria-hidden="true">
              {i.icon}
            </span>
            {open && <span className="truncate">{i.label}</span>}
          </NavLink>
        ))}
      </nav>
      <button
        onClick={handleLogout}
        title="Выйти"
        className={`m-2 flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm text-muted hover:bg-paper ${
          open ? "" : "justify-center"
        }`}
      >
        <span className="text-lg leading-none" aria-hidden="true">
          ⎋
        </span>
        {open && <span>Выйти</span>}
      </button>
    </aside>
  );
}
