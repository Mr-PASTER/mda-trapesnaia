import { useEffect, useState } from "react";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { useToast } from "../../components/ui/Toast";
import { useOperatorSettings, useSaveOperatorSettings } from "../../api/operator";

function toHm(value: string): string {
  return value.slice(0, 5);
}

export function SettingsPage() {
  const toast = useToast();
  const { data, isLoading } = useOperatorSettings();
  const save = useSaveOperatorSettings();
  const [generationDays, setGenerationDays] = useState(1);
  const [deadlineOffsetDays, setDeadlineOffsetDays] = useState(0);
  const [deadlineTime, setDeadlineTime] = useState("");

  useEffect(() => {
    if (data) {
      setGenerationDays(data.generation_days);
      setDeadlineOffsetDays(data.deadline_offset_days);
      setDeadlineTime(toHm(data.deadline_time));
    }
  }, [data]);

  const generationValid = Number.isInteger(generationDays) && generationDays >= 1;
  const offsetValid = Number.isInteger(deadlineOffsetDays) && deadlineOffsetDays >= 0;
  const canSave = generationValid && offsetValid && deadlineTime !== "" && !save.isPending;

  async function onSave() {
    try {
      await save.mutateAsync({
        generation_days: generationDays,
        deadline_offset_days: deadlineOffsetDays,
        deadline_time: `${deadlineTime}:00`,
      });
      toast("Сохранено");
    } catch {
      toast("Не удалось сохранить");
    }
  }

  const hour = deadlineTime ? deadlineTime.slice(0, 2) : "";

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Настройки</h1>
      {isLoading && <Spinner />}
      {data && (
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Горизонт генерации, дней</span>
            <Input
              type="number"
              min={1}
              step={1}
              value={generationDays}
              onChange={(e) => setGenerationDays(e.target.valueAsNumber)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Дедлайн за дней до даты</span>
            <Input
              type="number"
              min={0}
              step={1}
              value={deadlineOffsetDays}
              onChange={(e) => setDeadlineOffsetDays(e.target.valueAsNumber)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Время дедлайна</span>
            <Input type="time" value={deadlineTime} onChange={(e) => setDeadlineTime(e.target.value)} />
          </label>
          <div>
            <Button onClick={onSave} disabled={!canSave}>
              Сохранить
            </Button>
          </div>
          <p className="text-sm text-muted">
            Правка закрывается за {deadlineOffsetDays} дней до даты в {hour || "—"}:00
          </p>
        </div>
      )}
    </div>
  );
}
