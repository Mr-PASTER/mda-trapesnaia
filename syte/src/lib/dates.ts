const WEEKDAYS_FULL = [
  "Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота",
];
const WEEKDAYS_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];
const MONTHS_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

export function parseIso(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function iso(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function todayIso(): string {
  return iso(new Date());
}

export function addDays(value: string, days: number): string {
  const date = parseIso(value);
  date.setDate(date.getDate() + days);
  return iso(date);
}

export function rangeIso(from: string, to: string): string[] {
  const result: string[] = [];
  let current = from;
  while (current <= to) {
    result.push(current);
    current = addDays(current, 1);
  }
  return result;
}

export function formatDayShort(value: string): string {
  const date = parseIso(value);
  return `${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]}`;
}

export function formatWeekdayShort(value: string): string {
  return WEEKDAYS_SHORT[parseIso(value).getDay()];
}

export function formatDayFull(value: string): string {
  const date = parseIso(value);
  return `${WEEKDAYS_FULL[date.getDay()]}, ${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]} ${date.getFullYear()}`;
}
