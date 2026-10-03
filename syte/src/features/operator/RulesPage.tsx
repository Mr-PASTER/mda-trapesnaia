import { useState } from "react";
import {
  useCreateRule,
  useDeleteRule,
  useHalls,
  useRules,
  useUpdateRule,
  type Hall,
  type RuleKind,
  type ScheduleRule,
} from "../../api/operator";
import { ApiError } from "../../api/client";
import { MEAL_LABEL, MEAL_ORDER, type MealKind } from "../../lib/mealKind";
import { Table, Td, Th } from "../../components/ui/Table";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { Modal } from "../../components/ui/Modal";
import { EmptyState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/Toast";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const KIND_LABEL: Record<RuleKind, string> = {
  recurring: "Повторяющееся",
  one_off: "Одноразовое",
};

function weekdayLabel(days: number[]): string {
  return [...days]
    .sort((a, b) => a - b)
    .map((day) => WEEKDAYS[day] ?? "?")
    .join(", ");
}

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return year && month && day ? `${day}.${month}.${year}` : iso;
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function reportError(err: unknown, toast: (text: string) => void) {
  if (err instanceof ApiError && err.status === 400) {
    const detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail ?? "");
    if (detail.includes("invalid_rule")) {
      toast("Проверьте правило");
      return;
    }
  }
  toast("Не удалось выполнить");
}

export function RulesPage() {
  const toast = useToast();
  const { data: rules, isLoading } = useRules();
  const { data: halls } = useHalls();
  const remove = useDeleteRule();
  const update = useUpdateRule();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ScheduleRule | null>(null);

  const hallName = (id: string) => halls?.find((hall) => hall.id === id)?.name ?? "Зал";

  return (
    <div className="mx-auto max-w-5xl p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Правила расписания</h1>
        <Button onClick={() => setCreating(true)}>Добавить правило</Button>
      </div>

      {isLoading && <Spinner />}

      {rules && rules.length === 0 && (
        <EmptyState title="Правил пока нет" hint="Добавьте правило, чтобы выключать приёмы в отдельных залах" />
      )}

      {rules && rules.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Тип</Th>
              <Th>Что выключает</Th>
              <Th>Дни</Th>
              <Th>Залы</Th>
              <Th>Статус</Th>
              <Th className="text-right">Действия</Th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <Td>
                  <Badge tone={rule.kind === "recurring" ? "muted" : "accent"}>{KIND_LABEL[rule.kind]}</Badge>
                </Td>
                <Td>{rule.meal_kinds.map((kind) => MEAL_LABEL[kind]).join(", ") || "—"}</Td>
                <Td>
                  {rule.kind === "recurring"
                    ? rule.weekdays.length > 0
                      ? weekdayLabel(rule.weekdays)
                      : "—"
                    : rule.dates.length > 0
                      ? rule.dates.map(formatDate).join(", ")
                      : "—"}
                </Td>
                <Td>{rule.hall_ids.length > 0 ? rule.hall_ids.map(hallName).join(", ") : "—"}</Td>
                <Td>{rule.is_active ? <Badge>активно</Badge> : <Badge tone="accent">выключено</Badge>}</Td>
                <Td className="text-right">
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="ghost" onClick={() => setEditing(rule)}>
                      Изменить
                    </Button>
                    {rule.is_active ? (
                      <Button
                        variant="danger"
                        onClick={async () => {
                          try {
                            await remove.mutateAsync(rule.id);
                            toast("Правило выключено");
                          } catch (err) {
                            reportError(err, toast);
                          }
                        }}
                      >
                        Выключить
                      </Button>
                    ) : (
                      <Button
                        onClick={async () => {
                          try {
                            await update.mutateAsync({ id: rule.id, body: { is_active: true } });
                            toast("Правило включено");
                          } catch (err) {
                            reportError(err, toast);
                          }
                        }}
                      >
                        Включить
                      </Button>
                    )}
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      {creating && <RuleModal rule={null} halls={halls} onClose={() => setCreating(false)} />}
      {editing && <RuleModal rule={editing} halls={halls} onClose={() => setEditing(null)} />}
    </div>
  );
}

function RuleModal({
  rule,
  halls,
  onClose,
}: {
  rule: ScheduleRule | null;
  halls: Hall[] | undefined;
  onClose: () => void;
}) {
  const toast = useToast();
  const create = useCreateRule();
  const update = useUpdateRule();
  const isEdit = rule !== null;

  const [kind, setKind] = useState<RuleKind>(rule?.kind ?? "recurring");
  const [mealKinds, setMealKinds] = useState<MealKind[]>(rule?.meal_kinds ?? []);
  const [hallIds, setHallIds] = useState<string[]>(rule?.hall_ids ?? []);
  const [weekdays, setWeekdays] = useState<number[]>(rule?.weekdays ?? []);
  const [dates, setDates] = useState<string[]>(rule?.dates ?? []);
  const [newDate, setNewDate] = useState("");

  const pending = create.isPending || update.isPending;

  const valid =
    mealKinds.length >= 1 &&
    hallIds.length >= 1 &&
    (kind === "recurring"
      ? weekdays.length >= 1 && dates.length === 0
      : dates.length >= 1 && weekdays.length === 0);

  function changeKind(next: RuleKind) {
    setKind(next);
    if (next === "recurring") setDates([]);
    else setWeekdays([]);
  }

  function addDate() {
    if (!newDate || dates.includes(newDate)) return;
    setDates((prev) => [...prev, newDate].sort());
    setNewDate("");
  }

  async function save() {
    if (!valid) {
      toast("Заполните правило полностью");
      return;
    }
    const body = {
      kind,
      meal_kinds: mealKinds,
      hall_ids: hallIds,
      weekdays: kind === "recurring" ? [...weekdays].sort((a, b) => a - b) : [],
      dates: kind === "one_off" ? [...dates].sort() : [],
    };
    try {
      if (rule) await update.mutateAsync({ id: rule.id, body });
      else await create.mutateAsync(body);
      toast(isEdit ? "Правило сохранено" : "Правило создано");
      onClose();
    } catch (err) {
      reportError(err, toast);
    }
  }

  return (
    <Modal title={isEdit ? "Правило" : "Новое правило"} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Тип
          <Select value={kind} onChange={(e) => changeKind(e.target.value as RuleKind)}>
            <option value="recurring">{KIND_LABEL.recurring}</option>
            <option value="one_off">{KIND_LABEL.one_off}</option>
          </Select>
        </label>

        <div className="flex flex-col gap-1 text-sm">
          <span>Что выключаем</span>
          <div className="rounded-xl border border-border-strong bg-sunken p-2">
            {MEAL_ORDER.map((meal) => (
              <label key={meal} className="flex min-h-11 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={mealKinds.includes(meal)}
                  onChange={() => setMealKinds((prev) => toggle(prev, meal))}
                  className="h-4 w-4 accent-accent"
                />
                <span>{MEAL_LABEL[meal]}</span>
              </label>
            ))}
          </div>
        </div>

        {kind === "recurring" ? (
          <div className="flex flex-col gap-1 text-sm">
            <span>Дни недели</span>
            <div className="grid grid-cols-4 gap-1 rounded-xl border border-border-strong bg-sunken p-2">
              {WEEKDAYS.map((label, index) => (
                <label key={label} className="flex min-h-11 items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={weekdays.includes(index)}
                    onChange={() => setWeekdays((prev) => toggle(prev, index))}
                    className="h-4 w-4 accent-accent"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-1 text-sm">
            <span>Даты</span>
            <div className="flex gap-2">
              <Input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} />
              <Button type="button" variant="ghost" onClick={addDate} disabled={!newDate}>
                Добавить дату
              </Button>
            </div>
            {dates.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {dates.map((date) => (
                  <button
                    key={date}
                    type="button"
                    onClick={() => setDates((prev) => prev.filter((item) => item !== date))}
                    className="inline-flex min-h-11 items-center gap-1 rounded-xl border border-border px-3 text-sm text-ink hover:bg-sunken"
                  >
                    {formatDate(date)}
                    <span aria-hidden="true" className="text-muted">
                      ×
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-col gap-1 text-sm">
          <span>Залы</span>
          {halls ? (
            <div className="rounded-xl border border-border-strong bg-sunken p-2">
              {halls.map((hall) => (
                <label key={hall.id} className="flex min-h-11 items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={hallIds.includes(hall.id)}
                    onChange={() => setHallIds((prev) => toggle(prev, hall.id))}
                    className="h-4 w-4 accent-accent"
                  />
                  <span>
                    {hall.name}
                    {!hall.is_active && <span className="text-muted"> (выключен)</span>}
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <Spinner />
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={pending} onClick={save}>
            {isEdit ? "Сохранить" : "Создать"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
