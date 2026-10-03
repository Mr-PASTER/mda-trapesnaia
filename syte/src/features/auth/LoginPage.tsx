import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { login } from "../../api/auth";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { queryClient } from "../../app/queryClient";

export function LoginPage() {
  const [params] = useSearchParams();
  const expired = params.get("reason") === "expired";
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(loginValue, password);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Неверный логин или пароль" : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <h1 className="mb-4 text-xl font-semibold">Трапезная МДА</h1>
        {expired && (
          <p className="mb-3 rounded-lg bg-sunken px-3 py-2 text-xs text-muted">
            Сессия истекла — войдите заново
          </p>
        )}
        <form className="flex flex-col gap-3" onSubmit={onSubmit}>
          <label className="text-sm">
            Логин
            <Input
              value={loginValue}
              onChange={(e) => setLoginValue(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label className="text-sm">
            Пароль
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error && <p className="text-sm font-medium text-accent">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? "Входим…" : "Войти"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
