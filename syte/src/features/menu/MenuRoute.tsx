import { useCurrentUser } from "../../api/auth";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { MenuPage } from "./MenuPage";

/**
 * Маршрут «Моё меню»: питающиеся и админы видят сетку дней,
 * а оператор заявки не ведёт — ему показываем «скоро».
 */
export function MenuRoute() {
  const { data: me, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl p-4">
        <Spinner />
      </div>
    );
  }

  if (me?.role === "operator") {
    return (
      <div className="mx-auto max-w-5xl p-4">
        <header className="mb-4">
          <h1 className="text-xl font-semibold">Моё меню</h1>
        </header>
        <EmptyState
          title="Скоро"
          hint="Оператор не участвует в отметках о питании, поэтому раздел заявок для этой роли недоступен."
        />
      </div>
    );
  }

  return <MenuPage target={{ mode: "self" }} />;
}
