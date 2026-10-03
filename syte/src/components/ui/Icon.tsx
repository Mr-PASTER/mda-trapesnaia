// Одноцветные навигационные иконки (наследуют цвет текста).
const PATHS: Record<string, string[]> = {
  menu: ["M4 12h16a8 8 0 0 1-16 0Z", "M9 8c0-1.2 1-1.8 0-3", "M15 8c0-1.2 1-1.8 0-3"],
  tune: ["M4 7h16M4 12h16M4 17h16", "M9 5v4M15 10v4M7 15v4"],
  users: [
    "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M4 20c0-3 2.2-5 5-5s5 2 5 5",
    "M16 11a3 3 0 1 0 0-6",
    "M16 14.5c2.4.3 4 2.2 4 5.5",
  ],
  user: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M4 21c0-4 3.5-7 8-7s8 3 8 7"],
  hall: ["M4 21V8l8-5 8 5v13", "M9 21v-6h6v6"],
  bowl: ["M4 12h16a8 8 0 0 1-16 0Z", "M6 8h12"],
  rules: ["M12 3l7 4v6c0 4-3 7-7 8-4-1-7-4-7-8V7Z", "M9 12l2 2 4-4"],
  logs: ["M8 6h12M8 12h12M8 18h12", "M4 6h.01M4 12h.01M4 18h.01"],
  calendar: ["M4 6h16v14H4Z", "M4 10h16", "M8 3v4M16 3v4"],
  report: ["M7 3h7l4 4v14H7Z", "M10 12h7M10 16h7"],
  chart: ["M4 20h16", "M7 16v-5M12 16V8M17 16v-8"],
  logout: ["M15 12H4", "M8 8l-4 4 4 4", "M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"],
  lock: ["M6 11h12v9H6Z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3", "M12 14.5v2"],
};

export function Icon({
  name,
  className = "h-5 w-5",
  title,
}: {
  name: string;
  className?: string;
  title?: string;
}) {
  const paths = PATHS[name];
  if (!paths) return null;
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
