import { Navigate, Outlet, useLocation } from "react-router";
import { useCurrentUser } from "../api/auth";

const HOME_BY_ROLE: Record<string, string> = {
  eater: "/menu",
  admin: "/people",
  operator: "/operator/users",
  accountant: "/reports/daily",
};

export function RequireAuth() {
  const { data, isLoading, isError } = useCurrentUser();
  const location = useLocation();

  if (isLoading) return <div className="p-6 text-muted">Загрузка…</div>;
  if (isError || !data) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function RequireRole({ roles }: { roles: string[] }) {
  const { data, isLoading } = useCurrentUser();

  if (isLoading) return <div className="p-6 text-muted">Загрузка…</div>;
  if (data && !roles.includes(data.role)) {
    return <Navigate to={HOME_BY_ROLE[data.role] ?? "/login"} replace />;
  }
  return <Outlet />;
}

export function HomeRedirect() {
  const { data, isLoading } = useCurrentUser();

  if (isLoading) return <div className="p-6 text-muted">Загрузка…</div>;
  if (!data) return <Navigate to="/login" replace />;
  return <Navigate to={HOME_BY_ROLE[data.role] ?? "/menu"} replace />;
}
