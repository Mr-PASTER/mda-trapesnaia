import { useState } from "react";
import {
  useCreateUser,
  useDeleteUser,
  useHalls,
  useMealTypesAll,
  useOperatorUsers,
  useSetUserHalls,
  useSetUserPassword,
  useUpdateUser,
  type Hall,
  type MealTypeRow,
  type OperatorUser,
} from "../../api/operator";
import { ApiError } from "../../api/client";
import { Table, Td, Th } from "../../components/ui/Table";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/Toast";

type Role = OperatorUser["role"];

const ROLE_LABELS: Record<Role, string> = {
  eater: "Питающийся",
  admin: "Администратор",
  accountant: "Бухгалтер",
  operator: "Оператор",
};

const ROLE_HINTS: Record<Role, string> = {
  eater: "нужен ровно один зал",
  admin: "нужен минимум один зал",
  accountant: "залы не нужны",
  operator: "залы не нужны",
};

function hallsValid(role: Role, count: number): boolean {
  if (role === "eater") return count === 1;
  if (role === "admin") return count >= 1;
  return count === 0;
}

function reportError(err: unknown, toast: (text: string) => void) {
  if (err instanceof ApiError) {
    let detail = "";
    try {
      detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail ?? "");
    } catch {
      detail = "";
    }
    if (err.status === 409 && detail.includes("login_exists")) {
      toast("Такой логин уже занят");
      return;
    }
    if (err.status === 400 && detail.includes("invalid_halls")) {
      toast("Для этой роли нужно другое число залов");
      return;
    }
    if (err.status === 400 && detail.includes("invalid_meal_type")) {
      toast("Выберите активный тип питания");
      return;
    }
  }
  toast("Не удалось выполнить");
}

function HallCheckboxes({
  halls,
  selected,
  onToggle,
}: {
  halls: Hall[] | undefined;
  selected: string[];
  onToggle: (id: string) => void;
}) {
  if (!halls) return <Spinner />;
  return (
    <div className="rounded-xl border border-border p-2">
      {halls.map((hall) => (
        <label key={hall.id} className="flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={selected.includes(hall.id)}
            onChange={() => onToggle(hall.id)}
            className="h-4 w-4 accent-accent"
          />
          <span>
            {hall.name}
            {!hall.is_active && <span className="text-muted"> (выключен)</span>}
          </span>
        </label>
      ))}
    </div>
  );
}

function MealTypeSelect({
  mealTypes,
  value,
  onChange,
}: {
  mealTypes: MealTypeRow[] | undefined;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">— не выбран —</option>
      {(mealTypes ?? []).map((meal) => (
        <option key={meal.id} value={meal.id}>
          {meal.name}
          {meal.is_active ? "" : " (выключен)"}
        </option>
      ))}
    </Select>
  );
}

function RoleSelect({ value, onChange }: { value: Role; onChange: (role: Role) => void }) {
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value as Role)}>
      {(Object.keys(ROLE_LABELS) as Role[]).map((role) => (
        <option key={role} value={role}>
          {ROLE_LABELS[role]}
        </option>
      ))}
    </Select>
  );
}

export function UsersPage() {
  const toast = useToast();
  const { data: users, isLoading } = useOperatorUsers();
  const { data: halls } = useHalls();
  const { data: mealTypes } = useMealTypesAll();
  const remove = useDeleteUser();

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<OperatorUser | null>(null);
  const [hallsFor, setHallsFor] = useState<OperatorUser | null>(null);
  const [passwordFor, setPasswordFor] = useState<OperatorUser | null>(null);

  const hallName = (id: string) => halls?.find((hall) => hall.id === id)?.name ?? "Зал";

  return (
    <div className="mx-auto max-w-5xl p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Пользователи</h1>
        <Button onClick={() => setCreating(true)}>Добавить пользователя</Button>
      </div>

      {isLoading && <Spinner />}

      {users && (
        <Table>
          <thead>
            <tr>
              <Th>Логин</Th>
              <Th>ФИО</Th>
              <Th>Роль</Th>
              <Th>Залы</Th>
              <Th>Статус</Th>
              <Th className="text-right">Действия</Th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <Td>{user.login}</Td>
                <Td>{user.full_name}</Td>
                <Td>
                  <Badge tone={user.role === "eater" ? "muted" : "accent"}>{ROLE_LABELS[user.role]}</Badge>
                </Td>
                <Td>
                  {user.hall_ids.length > 0 ? user.hall_ids.map((id) => hallName(id)).join(", ") : "—"}
                </Td>
                <Td>{user.is_active ? <Badge>активен</Badge> : <Badge tone="accent">выключен</Badge>}</Td>
                <Td className="text-right">
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="ghost" onClick={() => setEditing(user)}>
                      Изменить
                    </Button>
                    <Button variant="ghost" onClick={() => setHallsFor(user)}>
                      Залы
                    </Button>
                    <Button variant="ghost" onClick={() => setPasswordFor(user)}>
                      Пароль
                    </Button>
                    {user.is_active && (
                      <Button
                        variant="danger"
                        onClick={async () => {
                          try {
                            await remove.mutateAsync({ id: user.id, hard: false });
                            toast("Пользователь выключен");
                          } catch (err) {
                            reportError(err, toast);
                          }
                        }}
                      >
                        Удалить
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      onClick={async () => {
                        if (!window.confirm(`Удалить «${user.login}» навсегда? Действие необратимо.`)) return;
                        try {
                          await remove.mutateAsync({ id: user.id, hard: true });
                          toast("Пользователь удалён навсегда");
                        } catch (err) {
                          reportError(err, toast);
                        }
                      }}
                    >
                      Удалить навсегда
                    </Button>
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      {creating && <CreateUserModal halls={halls} mealTypes={mealTypes} onClose={() => setCreating(false)} />}
      {editing && <EditUserModal user={editing} mealTypes={mealTypes} onClose={() => setEditing(null)} />}
      {hallsFor && <HallsModal user={hallsFor} halls={halls} onClose={() => setHallsFor(null)} />}
      {passwordFor && <PasswordModal user={passwordFor} onClose={() => setPasswordFor(null)} />}
    </div>
  );
}

function CreateUserModal({
  halls,
  mealTypes,
  onClose,
}: {
  halls: Hall[] | undefined;
  mealTypes: MealTypeRow[] | undefined;
  onClose: () => void;
}) {
  const toast = useToast();
  const create = useCreateUser();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("eater");
  const [hallIds, setHallIds] = useState<string[]>([]);
  const [mealTypeId, setMealTypeId] = useState("");

  const toggleHall = (id: string) =>
    setHallIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const canSave = Boolean(login.trim() && password && fullName.trim() && hallsValid(role, hallIds.length));

  return (
    <Modal title="Новый пользователь" onClose={onClose}>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Логин
          <Input value={login} onChange={(e) => setLogin(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Пароль
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          ФИО
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Роль
          <RoleSelect value={role} onChange={setRole} />
        </label>
        <div className="flex flex-col gap-1 text-sm">
          <span>
            Залы <span className="text-muted">— {ROLE_HINTS[role]}</span>
          </span>
          <HallCheckboxes halls={halls} selected={hallIds} onToggle={toggleHall} />
        </div>
        <label className="flex flex-col gap-1 text-sm">
          Тип питания по умолчанию (необязательно)
          <MealTypeSelect mealTypes={mealTypes} value={mealTypeId} onChange={setMealTypeId} />
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            disabled={!canSave || create.isPending}
            onClick={async () => {
              try {
                await create.mutateAsync({
                  login: login.trim(),
                  password,
                  full_name: fullName.trim(),
                  role,
                  hall_ids: hallIds,
                  default_meal_type_id: mealTypeId || null,
                });
                toast("Пользователь добавлен");
                onClose();
              } catch (err) {
                reportError(err, toast);
              }
            }}
          >
            Создать
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function EditUserModal({
  user,
  mealTypes,
  onClose,
}: {
  user: OperatorUser;
  mealTypes: MealTypeRow[] | undefined;
  onClose: () => void;
}) {
  const toast = useToast();
  const update = useUpdateUser();
  const [fullName, setFullName] = useState(user.full_name);
  const [role, setRole] = useState<Role>(user.role);
  const [mealTypeId, setMealTypeId] = useState(user.default_meal_type_id ?? "");

  return (
    <Modal title={`Изменить «${user.login}»`} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          ФИО
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Роль
          <RoleSelect value={role} onChange={setRole} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Тип питания по умолчанию (необязательно)
          <MealTypeSelect mealTypes={mealTypes} value={mealTypeId} onChange={setMealTypeId} />
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            disabled={!fullName.trim() || update.isPending}
            onClick={async () => {
              try {
                await update.mutateAsync({
                  id: user.id,
                  body: {
                    full_name: fullName.trim(),
                    role,
                    default_meal_type_id: mealTypeId || null,
                  },
                });
                toast("Сохранено");
                onClose();
              } catch (err) {
                reportError(err, toast);
              }
            }}
          >
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function HallsModal({
  user,
  halls,
  onClose,
}: {
  user: OperatorUser;
  halls: Hall[] | undefined;
  onClose: () => void;
}) {
  const toast = useToast();
  const setHalls = useSetUserHalls();
  const [hallIds, setHallIds] = useState<string[]>(user.hall_ids);

  const toggleHall = (id: string) =>
    setHallIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const canSave = hallsValid(user.role, hallIds.length);

  return (
    <Modal title={`Залы «${user.login}»`} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <span className="text-sm text-muted">
          Роль: {ROLE_LABELS[user.role]} — {ROLE_HINTS[user.role]}
        </span>
        <HallCheckboxes halls={halls} selected={hallIds} onToggle={toggleHall} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            disabled={!canSave || setHalls.isPending}
            onClick={async () => {
              try {
                await setHalls.mutateAsync({ id: user.id, hallIds });
                toast("Залы обновлены");
                onClose();
              } catch (err) {
                reportError(err, toast);
              }
            }}
          >
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function PasswordModal({ user, onClose }: { user: OperatorUser; onClose: () => void }) {
  const toast = useToast();
  const savePassword = useSetUserPassword();
  const [password, setPassword] = useState("");

  return (
    <Modal title={`Новый пароль «${user.login}»`} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Пароль
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            disabled={!password || savePassword.isPending}
            onClick={async () => {
              try {
                await savePassword.mutateAsync({ id: user.id, password });
                toast("Пароль изменён");
                onClose();
              } catch (err) {
                reportError(err, toast);
              }
            }}
          >
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  );
}
