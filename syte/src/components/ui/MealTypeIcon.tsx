// Одноцветные линейные иконки типов питания.
// Цвет наследуется от текста (currentColor) — иконки всегда монохромные.
const ICONS: Record<string, string[]> = {
  // мясо — «ломоть»: круг с вырезкой
  meat: [
    "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z",
    "M9.5 12a2.5 2.5 0 1 0 5 0 2.5 2.5 0 0 0-5 0Z",
  ],
  // рыба — тело с хвостом и глазом
  fish: [
    "M2 12c3.5-4 7.5-6 11.5-6 2.5 0 4.5 1 6 3l2.5-3v12l-2.5-3c-1.5 2-3.5 3-6 3-4 0-8-2-11.5-6Z",
    "M7 11h.01",
  ],
  // пост — росток с двумя листьями
  lent: [
    "M12 21v-7",
    "M12 14c0-3 2.5-5 6-5 0 3-2.5 5-6 5Z",
    "M12 14c0-2.6-2-4.3-5-4.3 0 2.6 2 4.3 5 4.3Z",
  ],
};

// фолбэк для незнакомых ключей — нейтральная «миска», тоже монохромная
const FALLBACK = ["M3 11h18a9 9 0 0 1-18 0Z"];

export function MealTypeIcon({
  icon,
  className = "",
  title,
}: {
  icon: string | null;
  className?: string;
  title?: string;
}) {
  if (!icon) return null;
  const paths = ICONS[icon] ?? FALLBACK;

  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      {paths.map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
