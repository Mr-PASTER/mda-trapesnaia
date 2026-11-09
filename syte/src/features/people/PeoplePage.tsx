import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { usePeople } from "../../api/admin";
import { useCurrentUser } from "../../api/auth";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";

type Source = "ldap" | "local";

export function PeoplePage() {
  const navigate = useNavigate();
  const { data: me } = useCurrentUser();
  const { data: people, isLoading, isError } = usePeople();
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<Source>("ldap");

  const hallName = useMemo(() => {
    const map = new Map<string, string>();
    (me?.halls ?? []).forEach((h) => map.set(h.id, h.name));
    return map;
  }, [me]);

  const ldapPeople = useMemo(
    () => (people ?? []).filter((p) => p.auth_source === "ldap"),
    [people],
  );
  const localPeople = useMemo(
    () => (people ?? []).filter((p) => p.auth_source !== "ldap"),
    [people],
  );

  const filtered = useMemo(() => {
    const list = source === "ldap" ? ldapPeople : localPeople;
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (p) => p.full_name.toLowerCase().includes(q) || p.login.toLowerCase().includes(q),
    );
  }, [ldapPeople, localPeople, query, source]);

  const tabClass = (active: boolean) =>
    `min-h-11 rounded-xl border px-4 text-sm ${
      active ? "border-accent bg-surface font-medium" : "border-border text-muted"
    }`;

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Питающиеся</h1>

      <div className="mb-4 flex gap-2" role="tablist" aria-label="Источник пользователей">
        <button
          type="button"
          role="tab"
          aria-selected={source === "ldap"}
          onClick={() => setSource("ldap")}
          className={tabClass(source === "ldap")}
        >
          Студенты · {ldapPeople.length}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={source === "local"}
          onClick={() => setSource("local")}
          className={tabClass(source === "local")}
        >
          Внешние · {localPeople.length}
        </button>
      </div>

      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск по имени или логину"
        aria-label="Поиск"
      />

      {isLoading && (
        <div className="mt-4">
          <Spinner />
        </div>
      )}
      {isError && <p className="mt-4 text-sm font-medium text-accent">Не удалось загрузить список</p>}

      {!isLoading && !isError && filtered.length === 0 && (
        <div className="mt-4">
          <EmptyState
            title={
              query
                ? "Никого не найдено"
                : source === "ldap"
                  ? "В каталоге пока нет студентов"
                  : "Внешних пользователей нет"
            }
            hint={query ? "Попробуйте изменить запрос" : undefined}
          />
        </div>
      )}

      <ul className="mt-4 flex flex-col gap-2">
        {filtered.map((person) => (
          <li key={person.id}>
            <button
              type="button"
              onClick={() => navigate(`/people/${person.id}`)}
              className="flex min-h-12 w-full flex-col items-start rounded-2xl border border-border bg-surface px-4 py-3 text-left shadow-card hover:border-accent/60"
            >
              <span className="text-sm font-medium">{person.full_name}</span>
              <span className="text-xs text-muted">
                {person.login}
                {person.hall_ids.length > 0 &&
                  ` · ${person.hall_ids.map((id) => hallName.get(id) ?? "Зал").join(", ")}`}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
