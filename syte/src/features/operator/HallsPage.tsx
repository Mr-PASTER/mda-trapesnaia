import { useState } from "react";
import { Table, Td, Th } from "../../components/ui/Table";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Spinner } from "../../components/ui/Spinner";
import { useToast } from "../../components/ui/Toast";
import { useCreateHall, useDeleteHall, useHalls, useUpdateHall } from "../../api/operator";
import { ApiError } from "../../api/client";

export function HallsPage() {
  const toast = useToast();
  const { data, isLoading } = useHalls();
  const create = useCreateHall();
  const update = useUpdateHall();
  const remove = useDeleteHall();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);

  function report(err: unknown) {
    if (err instanceof ApiError && err.status === 409) toast("Зал с таким названием уже есть");
    else if (err instanceof ApiError && err.status === 400) toast("Нельзя: операция запрещена");
    else toast("Не удалось выполнить");
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Залы</h1>

      <div className="mb-4 flex gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название зала" />
        <Button
          onClick={async () => {
            try {
              await create.mutateAsync(name.trim());
              setName("");
              toast("Зал добавлен");
            } catch (err) {
              report(err);
            }
          }}
          disabled={!name.trim() || create.isPending}
        >
          Добавить
        </Button>
      </div>

      {isLoading && <Spinner />}
      {data && (
        <Table>
          <thead>
            <tr>
              <Th>Название</Th>
              <Th>Статус</Th>
              <Th className="text-right">Действия</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((hall) => (
              <tr key={hall.id}>
                <Td>
                  {editing?.id === hall.id ? (
                    <Input value={editing.name} onChange={(e) => setEditing({ id: hall.id, name: e.target.value })} />
                  ) : (
                    hall.name
                  )}
                </Td>
                <Td>{hall.is_active ? <Badge>активен</Badge> : <Badge tone="accent">выключен</Badge>}</Td>
                <Td className="text-right">
                  {editing?.id === hall.id ? (
                    <Button
                      variant="ghost"
                      onClick={async () => {
                        try {
                          await update.mutateAsync({ id: hall.id, name: editing.name.trim() });
                          setEditing(null);
                          toast("Сохранено");
                        } catch (err) {
                          report(err);
                        }
                      }}
                    >
                      Сохранить
                    </Button>
                  ) : (
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing({ id: hall.id, name: hall.name })}>
                        Переименовать
                      </Button>
                      {hall.is_active && (
                        <Button
                          variant="danger"
                          onClick={async () => {
                            try {
                              await remove.mutateAsync(hall.id);
                              toast("Зал выключен");
                            } catch (err) {
                              report(err);
                            }
                          }}
                        >
                          Выключить
                        </Button>
                      )}
                    </div>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
