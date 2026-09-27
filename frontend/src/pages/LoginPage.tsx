import { useState } from "react";
import { useAuth } from "../context/AuthProvider.tsx";

const inputClass = "mt-1 h-10 w-full rounded-md border border-[var(--line)] px-3 font-sans text-sm";

export const LoginPage = () => {
  const { login, error, status, canRegister, showRegister } = useAuth();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ username: "", password: "" });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    void login(form)
      .catch(() => null)
      .finally(() => setBusy(false));
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-[var(--paper)] p-8">
      <section className="w-full max-w-md rounded-xl border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[var(--shadow)]">
        <p className="text-[11px] tracking-[0.2em] text-[var(--muted)] uppercase">Sign in</p>
        <h1 className="mt-2 text-3xl">{status?.shop?.name || "Shop Manager"}</h1>
        <p className="mt-2 font-sans text-sm text-[var(--muted)]">
          {status?.registered
            ? "Enter your credentials to open this shop."
            : "Sign in if you already have an account, or register this install as a new shop."}
        </p>
        {error ? <p className="mt-4 font-sans text-sm text-[var(--danger)]">{error}</p> : null}
        <form className="mt-6 grid gap-3" onSubmit={submit}>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Username</span>
            <input
              className={inputClass}
              autoComplete="username"
              required
              value={form.username}
              onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
            />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Password</span>
            <input
              className={inputClass}
              type="password"
              autoComplete="current-password"
              required
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            />
          </label>
          <button
            type="submit"
            disabled={busy || !status?.registered}
            className="mt-2 h-11 rounded-md bg-[var(--accent)] font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        {canRegister ? (
          <div className="mt-6 border-t border-[var(--line)] pt-5 font-sans text-sm">
            <p className="text-[var(--muted)]">New install? Set up your shop on this computer.</p>
            <button
              type="button"
              className="mt-3 h-10 w-full rounded-md border border-[var(--line)] px-3 text-[var(--ink)] hover:bg-[var(--paper)]"
              onClick={showRegister}
            >
              Register a shop
            </button>
          </div>
        ) : (
          <p className="mt-6 font-sans text-xs text-[var(--muted)]">
            This install already has a shop. Contact the owner if you need a password reset.
          </p>
        )}
      </section>
    </div>
  );
};
