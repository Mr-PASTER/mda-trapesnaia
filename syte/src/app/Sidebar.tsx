import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router";
import { logout, useCurrentUser } from "../api/auth";
import { queryClient } from "./queryClient";
import { readLocal, writeLocal } from "../lib/storage";
import { Icon } from "../components/ui/Icon";

type Item = { to: string; label: string; icon: string };

const SIDEBAR_KEY = "mda.sidebar";

const NAV: Record<string, Item[]> = {
  eater: [
    { to: "/menu", label: "Моё меню", icon: "menu" },
    { to: "/settings", label: "Настройки", icon: "tune" },
  ],
  admin: [
    { to: "/people", label: "Питающиеся", icon: "users" },
    { to: "/settings", label: "Настройки", icon: "tune" },
  ],
  // Оператор имеет доступ ко всем панелям.
  operator: [
    { to: "/operator/users", label: "Пользователи", icon: "user" },
    { to: "/operator/halls", label: "Залы", icon: "hall" },
    { to: "/operator/meal-types", label: "Типы питания", icon: "bowl" },
    { to: "/operator/rules", label: "Правила", icon: "rules" },
    { to: "/operator/settings", label: "Настройки системы", icon: "tune" },
    { to: "/operator/logs", label: "Логи", icon: "logs" },
    { to: "/operator/calendar", label: "Календарь", icon: "calendar" },
    { to: "/people", label: "Питающиеся", icon: "users" },
    { to: "/reports/daily", label: "Отчёт за день", icon: "report" },
    { to: "/reports/period", label: "Отчёт за период", icon: "chart" },
    { to: "/menu", label: "Моё меню", icon: "menu" },
  ],
  accountant: [
    { to: "/reports/daily", label: "Отчёт за день", icon: "report" },
    { to: "/reports/period", label: "Отчёт за период", icon: "chart" },
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
              } ${isActive ? "bg-accent text-on-accent" : "text-ink hover:bg-paper"}`
            }
          >
            <Icon name={i.icon} />
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
        <Icon name="logout" />
        {open && <span>Выйти</span>}
      </button>
    </aside>
  );
}
