import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { usePeople } from "../../api/admin";
import { useCurrentUser } from "../../api/auth";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";

export function PeoplePage() {
  const navigate = useNavigate();
  const { data: me } = useCurrentUser();
  const { data: people, isLoading, isError } = usePeople();
  const [query, setQuery] = useState("");

  const hallName = useMemo(() => {
    const map = new Map<string, string>();
    (me?.halls ?? []).forEach((h) => map.set(h.id, h.name));
    return map;
  }, [me]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = people ?? [];
    if (!q) return list;
    return list.filter(
      (p) => p.full_name.toLowerCase().includes(q) || p.login.toLowerCase().includes(q),
    );
  }, [people, query]);

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Питающиеся</h1>

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
            title={query ? "Никого не найдено" : "В ваших залах пока нет питающихся"}
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
