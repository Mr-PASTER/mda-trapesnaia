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
