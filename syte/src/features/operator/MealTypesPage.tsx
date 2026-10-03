import { useState } from "react";
import { Table, Td, Th } from "../../components/ui/Table";
import { Select } from "../../components/ui/Select";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Spinner } from "../../components/ui/Spinner";
import { MealTypeIcon } from "../../components/ui/MealTypeIcon";
import { useToast } from "../../components/ui/Toast";
import { useCreateMealType, useDeleteMealType, useMealTypesAll, useUpdateMealType } from "../../api/operator";
import { ApiError } from "../../api/client";

const ICON_OPTIONS = [
  { value: "meat", label: "Мясное" },
  { value: "lent", label: "Постное" },
  { value: "fish", label: "Рыбное" },
];

const EMPTY_ICON = "Без иконки";

type IconSelectProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  "aria-label"?: string;
};

function IconSelect({ value, onChange, className, ...rest }: IconSelectProps) {
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)} className={className} {...rest}>
      <option value="">{EMPTY_ICON}</option>
      {ICON_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </Select>
  );
}

export function MealTypesPage() {
  const toast = useToast();
  const { data, isLoading } = useMealTypesAll();
  const create = useCreateMealType();
  const update = useUpdateMealType();
  const remove = useDeleteMealType();
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [editing, setEditing] = useState<{ id: string; name: string; icon: string; sortOrder: string } | null>(null);

  function report(err: unknown) {
    const detail = err instanceof ApiError ? err.detail : undefined;
    const code = typeof detail === "string" ? detail : (detail as { code?: string } | undefined)?.code;
    if (code === "last_meal_type") toast("Нельзя выключить последний тип питания");
    else if (err instanceof ApiError && err.status === 409) toast("Тип питания с таким названием уже есть");
    else if (err instanceof ApiError && err.status === 400) toast("Нельзя: операция запрещена");
    else toast("Не удалось выполнить");
  }

  function resetForm() {
    setName("");
    setIcon("");
    setSortOrder("0");
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Типы питания</h1>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Название типа питания"
          className="min-w-40 flex-1"
        />
        <div className="flex items-center gap-2">
          <MealTypeIcon icon={icon || null} className="h-5 w-5 text-muted" />
          <IconSelect value={icon} onChange={setIcon} className="w-36" aria-label="Иконка" />
        </div>
        <Input
          type="number"
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value)}
          className="w-24"
          aria-label="Порядок"
        />
        <Button
          onClick={async () => {
            try {
              await create.mutateAsync({ name: name.trim(), sort_order: Number(sortOrder) || 0, icon: icon || null });
              resetForm();
              toast("Тип питания добавлен");
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
              <Th>Иконка</Th>
              <Th>Название</Th>
              <Th>Порядок</Th>
              <Th>Статус</Th>
              <Th className="text-right">Действия</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((type) => (
              <tr key={type.id}>
                <Td>
                  {editing?.id === type.id ? (
                    <IconSelect
                      value={editing.icon}
                      onChange={(value) => setEditing({ ...editing, icon: value })}
                      className="w-32"
                      aria-label="Иконка"
                    />
                  ) : (
                    <MealTypeIcon icon={type.icon} className="h-5 w-5 text-muted" />
                  )}
                </Td>
                <Td>
                  {editing?.id === type.id ? (
                    <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
                  ) : (
                    type.name
                  )}
                </Td>
                <Td>
                  {editing?.id === type.id ? (
                    <Input
                      type="number"
                      value={editing.sortOrder}
                      onChange={(e) => setEditing({ ...editing, sortOrder: e.target.value })}
                      className="w-24"
                      aria-label="Порядок"
                    />
                  ) : (
                    type.sort_order
                  )}
                </Td>
                <Td>{type.is_active ? <Badge>активен</Badge> : <Badge tone="accent">выключен</Badge>}</Td>
                <Td className="text-right">
                  {editing?.id === type.id ? (
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing(null)}>
                        Отмена
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={async () => {
                          try {
                            await update.mutateAsync({
                              id: type.id,
                              body: {
                                name: editing.name.trim(),
                                sort_order: Number(editing.sortOrder) || 0,
                                icon: editing.icon || null,
                              },
                            });
                            setEditing(null);
                            toast("Сохранено");
                          } catch (err) {
                            report(err);
                          }
                        }}
                      >
                        Сохранить
                      </Button>
                    </div>
                  ) : (
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        onClick={() =>
                          setEditing({
                            id: type.id,
                            name: type.name,
                            icon: type.icon ?? "",
                            sortOrder: String(type.sort_order),
                          })
                        }
                      >
                        Изменить
                      </Button>
                      {type.is_active && (
                        <Button
                          variant="danger"
                          onClick={async () => {
                            try {
                              await remove.mutateAsync(type.id);
                              toast("Тип питания выключен");
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
