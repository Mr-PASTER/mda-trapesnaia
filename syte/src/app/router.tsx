import { createBrowserRouter } from "react-router";
import { RequireAuth, RequireRole, HomeRedirect } from "./guards";
import { AppLayout } from "./AppLayout";
import { LoginPage } from "../features/auth/LoginPage";
import { MenuPage } from "../features/menu/MenuPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { PeoplePage } from "../features/people/PeoplePage";
import { PersonMenuPage, PersonSettingsPage } from "../features/people/PersonRoutes";
import { DailyReportPage } from "../features/reports/DailyReportPage";
import { PeriodReportPage } from "../features/reports/PeriodReportPage";
import { HallsPage } from "../features/operator/HallsPage";
import { MealTypesPage } from "../features/operator/MealTypesPage";
import { UsersPage } from "../features/operator/UsersPage";
import { RulesPage } from "../features/operator/RulesPage";
import { LogsPage } from "../features/operator/LogsPage";
import { CalendarPage } from "../features/operator/CalendarPage";
import { SettingsPage as OperatorSettingsPage } from "../features/operator/SettingsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/menu", element: <MenuPage target={{ mode: "self" }} /> },
          { path: "/settings", element: <SettingsPage target={{ mode: "self" }} /> },
          {
            element: <RequireRole roles={["admin", "operator"]} />,
            children: [
              { path: "/people", element: <PeoplePage /> },
              { path: "/people/:userId", element: <PersonMenuPage /> },
              { path: "/people/:userId/settings", element: <PersonSettingsPage /> },
            ],
          },
          {
            element: <RequireRole roles={["accountant", "operator"]} />,
            children: [
              { path: "/reports/daily", element: <DailyReportPage /> },
              { path: "/reports/period", element: <PeriodReportPage /> },
            ],
          },
          {
            element: <RequireRole roles={["operator"]} />,
            children: [
              { path: "/operator/users", element: <UsersPage /> },
              { path: "/operator/halls", element: <HallsPage /> },
              { path: "/operator/meal-types", element: <MealTypesPage /> },
              { path: "/operator/rules", element: <RulesPage /> },
              { path: "/operator/settings", element: <OperatorSettingsPage /> },
              { path: "/operator/logs", element: <LogsPage /> },
              { path: "/operator/calendar", element: <CalendarPage /> },
            ],
          },
          { path: "/", element: <HomeRedirect /> },
        ],
      },
    ],
  },
  { path: "*", element: <HomeRedirect /> },
]);
