import { createBrowserRouter } from "react-router";
import { RequireAuth, RequireRole, HomeRedirect } from "./guards";
import { AppLayout } from "./AppLayout";
import { LoginPage } from "../features/auth/LoginPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/menu", element: <div className="p-6">Меню (F2)</div> },
          { path: "/settings", element: <div className="p-6">Настройки (F3)</div> },
          {
            element: <RequireRole roles={["admin"]} />,
            children: [
              { path: "/people", element: <div className="p-6">Питающиеся (F4)</div> },
              { path: "/people/:userId", element: <div className="p-6">Карточка питающегося (F4)</div> },
            ],
          },
          {
            element: <RequireRole roles={["accountant"]} />,
            children: [
              { path: "/reports/daily", element: <div className="p-6">Отчёт за день (F5)</div> },
              { path: "/reports/period", element: <div className="p-6">Отчёт за период (F5)</div> },
            ],
          },
          {
            element: <RequireRole roles={["operator"]} />,
            children: [
              { path: "/operator/users", element: <div className="p-6">Пользователи (F6)</div> },
              { path: "/operator/halls", element: <div className="p-6">Залы (F6)</div> },
              { path: "/operator/meal-types", element: <div className="p-6">Типы питания (F6)</div> },
              { path: "/operator/rules", element: <div className="p-6">Правила (F6)</div> },
              { path: "/operator/settings", element: <div className="p-6">Настройки (F6)</div> },
              { path: "/operator/logs", element: <div className="p-6">Логи (F6)</div> },
              { path: "/operator/calendar", element: <div className="p-6">Календарь (F6)</div> },
            ],
          },
          { path: "/", element: <HomeRedirect /> },
        ],
      },
    ],
  },
  { path: "*", element: <HomeRedirect /> },
]);
