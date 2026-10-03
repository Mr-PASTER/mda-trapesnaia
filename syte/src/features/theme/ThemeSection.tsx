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
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <h2 className="mb-3 text-base font-semibold">Тема оформления</h2>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => choose(option.value)}
            aria-pressed={theme === option.value}
            className={`min-h-11 rounded-xl px-4 text-sm ${
              theme === option.value ? "bg-accent text-on-accent" : "border border-border text-muted"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
}
