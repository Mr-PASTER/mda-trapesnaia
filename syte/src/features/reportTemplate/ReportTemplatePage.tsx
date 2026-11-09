import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import {
  useCatalogHalls,
  useReportTemplate,
  useSaveReportTemplate,
  type HallBrief,
  type TemplateGroup,
  type TemplateTotal,
} from "../../api/reportTemplate";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { useToast } from "../../components/ui/Toast";

function move(list: string[], index: number, delta: number): string[] {
  const next = [...list];
  const target = index + delta;
  if (target < 0 || target >= next.length) return next;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

function HallList({ halls, selected, onChange }: {
  halls: HallBrief[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const byId = new Map(halls.map((h) => [h.id, h.name]));
  const free = halls.filter((h) => !selected.includes(h.id));
  return (
    <div className="flex flex-col gap-2">
      <div className="rounded-xl border border-border-strong bg-sunken p-2">
        {selected.length === 0 && <p className="p-2 text-sm text-muted">Залы не выбраны</p>}
        {selected.map((id, index) => (
          <div key={id} className="flex min-h-11 items-center gap-2 text-sm">
            <span className="flex-1">{byId.get(id) ?? "Зал"}</span>
            <button type="button" onClick={() => onChange(move(selected, index, -1))}
                    className="min-h-9 rounded-lg border border-border px-2" aria-label="Выше">↑</button>
            <button type="button" onClick={() => onChange(move(selected, index, 1))}
                    className="min-h-9 rounded-lg border border-border px-2" aria-label="Ниже">↓</button>
            <button type="button" onClick={() => onChange(selected.filter((x) => x !== id))}
                    className="min-h-9 rounded-lg border border-border px-2" aria-label="Убрать">×</button>
          </div>
        ))}
      </div>
      <Select value="" onChange={(e) => e.target.value && onChange([...selected, e.target.value])}>
        <option value="">— добавить зал —</option>
        {free.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
      </Select>
    </div>
  );
}

function GroupCard({ group, halls, onChange, onRemove }: {
  group: TemplateGroup;
  halls: HallBrief[];
  onChange: (next: TemplateGroup) => void;
  onRemove: () => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input value={group.name} placeholder="Название группы"
               onChange={(e) => onChange({ ...group, name: e.target.value })} />
        <Button variant="ghost" onClick={onRemove}>Удалить</Button>
      </div>
      <label className="mb-3 flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={group.show_subtotal}
               onChange={(e) => onChange({ ...group, show_subtotal: e.target.checked })}
               className="h-4 w-4 accent-accent" />
        Показывать подытог
      </label>
      <HallList halls={halls} selected={group.hall_ids}
                onChange={(hall_ids) => onChange({ ...group, hall_ids })} />
    </section>
  );
}

function TotalCard({ total, halls, onChange, onRemove }: {
  total: TemplateTotal;
  halls: HallBrief[];
  onChange: (next: TemplateTotal) => void;
  onRemove: () => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input value={total.name} placeholder="Название итога"
               onChange={(e) => onChange({ ...total, name: e.target.value })} />
        <Button variant="ghost" onClick={onRemove}>Удалить</Button>
      </div>
      <label className="mb-3 flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={total.all_halls}
               onChange={(e) => onChange({ ...total, all_halls: e.target.checked, hall_ids: [] })}
               className="h-4 w-4 accent-accent" />
        Все залы
      </label>
      {!total.all_halls && (
        <HallList halls={halls} selected={total.hall_ids}
                  onChange={(hall_ids) => onChange({ ...total, hall_ids })} />
      )}
    </section>
  );
}

export function ReportTemplatePage() {
  const toast = useToast();
  const { data: template, isLoading } = useReportTemplate();
  const { data: halls } = useCatalogHalls();
  const save = useSaveReportTemplate();
  const [groups, setGroups] = useState<TemplateGroup[]>([]);
  const [totals, setTotals] = useState<TemplateTotal[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!template || loaded) return;
    setGroups(template.groups);
    setTotals(template.totals);
    setLoaded(true);
  }, [template, loaded]);

  async function onSave() {
    try {
      await save.mutateAsync({ groups, totals });
      toast("Шаблон сохранён");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        toast("Проверьте группы и итоги");
        return;
      }
      toast("Не удалось сохранить");
    }
  }

  if (isLoading) return <div className="p-4"><Spinner /></div>;

  return (
    <div className="mx-auto max-w-3xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Конструктор отчёта</h1>
        <Button onClick={onSave} disabled={save.isPending}>Сохранить</Button>
      </header>

      <h2 className="mb-2 text-base font-semibold">Группы залов</h2>
      <div className="mb-4 flex flex-col gap-3">
        {groups.map((group, index) => (
          <GroupCard key={index} group={group} halls={halls ?? []}
                     onChange={(next) => setGroups((prev) => prev.map((g, i) => (i === index ? next : g)))}
                     onRemove={() => setGroups((prev) => prev.filter((_, i) => i !== index))} />
        ))}
        <Button variant="ghost"
                onClick={() => setGroups((prev) => [...prev, { name: "", show_subtotal: true, hall_ids: [] }])}>
          Добавить группу
        </Button>
      </div>

      <h2 className="mb-2 text-base font-semibold">Общие итоги</h2>
      <div className="flex flex-col gap-3">
        {totals.map((total, index) => (
          <TotalCard key={index} total={total} halls={halls ?? []}
                     onChange={(next) => setTotals((prev) => prev.map((t, i) => (i === index ? next : t)))}
                     onRemove={() => setTotals((prev) => prev.filter((_, i) => i !== index))} />
        ))}
        <Button variant="ghost"
                onClick={() => setTotals((prev) => [...prev, { name: "", all_halls: false, hall_ids: [] }])}>
          Добавить итог
        </Button>
      </div>
    </div>
  );
}
