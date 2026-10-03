import { useState } from "react";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { useToast } from "../../components/ui/Toast";
import { useRegenerateDays } from "../../api/operator";
import { addDays, todayIso } from "../../lib/dates";

export function CalendarPage() {
  const toast = useToast();
  const regenerate = useRegenerateDays();
  const [from, setFrom] = useState(todayIso());
  const [to, setTo] = useState(addDays(todayIso(), 30));

  const valid = from !== "" && to !== "" && from <= to;

  async function onRegenerate() {
    try {
      await regenerate.mutateAsync({ from, to });
      toast("Календарь перегенерирован");
    } catch {
      toast("Не удалось перегенерировать");
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Календарь</h1>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">С</span>
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">По</span>
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <p className="text-sm text-muted">
          Диапазон: {from} — {to}
        </p>
        <p className="text-sm text-muted">
          Изменение правил применяется к сгенерированным дням в этом диапазоне
        </p>
        <div>
          <Button onClick={onRegenerate} disabled={!valid || regenerate.isPending}>
            Перегенерировать
          </Button>
        </div>
      </div>
    </div>
  );
}
