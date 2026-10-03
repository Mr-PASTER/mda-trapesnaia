import { useState } from "react";
import { useLogs } from "../../api/operator";
import { todayIso } from "../../lib/dates";
import { Table, Td, Th } from "../../components/ui/Table";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${day}.${month}.${year} ${hours}:${minutes}`;
}

export function LogsPage() {
  const [from, setFrom] = useState(todayIso());
  const [to, setTo] = useState(todayIso());
  const [applied, setApplied] = useState({ from: todayIso(), to: todayIso() });
  const { data, isLoading, isError } = useLogs(applied);

  return (
    <div className="mx-auto max-w-5xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Логи</h1>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          С
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-sm">
          По
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <Button onClick={() => setApplied({ from, to })}>Показать</Button>
      </div>

      {isLoading && <Spinner />}
      {isError && <p className="text-sm font-medium text-accent">Не удалось загрузить логи</p>}
      {data && data.length === 0 && <EmptyState title="За выбранный период логов нет" />}
      {data && data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Время</Th>
              <Th>Действие</Th>
              <Th>Тип сущности</Th>
              <Th>ID сущности</Th>
              <Th>Пользователь</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((log) => (
              <tr key={log.id}>
                <Td>{formatDateTime(log.created_at)}</Td>
                <Td>{log.action}</Td>
                <Td>{log.entity_type}</Td>
                <Td>{log.entity_id ?? "—"}</Td>
                <Td>{log.user_id ?? "—"}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
