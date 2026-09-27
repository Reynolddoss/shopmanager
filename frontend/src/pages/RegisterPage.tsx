import { useState } from "react";
import { useAuth } from "../context/AuthProvider.tsx";

const inputClass = "mt-1 h-10 w-full rounded-md border border-[var(--line)] px-3 font-sans text-sm";

export const RegisterPage = () => {
  const { register, error, showLogin, canRegister } = useAuth();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    shop_name: "",
    owner_name: "",
    username: "",
    password: "",
    confirm_password: "",
    phone: "",
    address: "",
    gstin: "",
    invoice_prefix: "SH",
    email: "",
  });

  const setField = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    void register(form)
      .catch(() => null)
      .finally(() => setBusy(false));
  };

  if (!canRegister) {
    return (
      <div className="flex min-h-full items-center justify-center bg-[var(--paper)] p-8">
        <section className="w-full max-w-md rounded-xl border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[var(--shadow)]">
          <h1 className="text-2xl">Shop already registered</h1>
          <p className="mt-2 font-sans text-sm text-[var(--muted)]">
            This install already has an owner account. Sign in instead.
          </p>
          <button
            type="button"
            className="mt-6 h-10 w-full rounded-md bg-[var(--accent)] font-sans text-sm text-[var(--on-accent)]"
            onClick={showLogin}
          >
            Back to sign in
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-[var(--paper)] p-8">
      <section className="w-full max-w-lg rounded-xl border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[var(--shadow)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] tracking-[0.2em] text-[var(--muted)] uppercase">First-time setup</p>
            <h1 className="mt-2 text-3xl">Register your shop</h1>
          </div>
          <button
            type="button"
            className="shrink-0 font-sans text-sm text-[var(--muted)] underline-offset-2 hover:underline"
            onClick={showLogin}
          >
            Back to sign in
          </button>
        </div>
        <p className="mt-2 font-sans text-sm text-[var(--muted)]">
          One install equals one shop. Enter your business details and create the owner account for this computer.
        </p>
        {error ? <p className="mt-4 font-sans text-sm text-[var(--danger)]">{error}</p> : null}
        <form className="mt-6 grid gap-3" onSubmit={submit}>
          {[
            ["shop_name", "Shop name", "text"],
            ["owner_name", "Owner name", "text"],
            ["username", "Username", "text"],
            ["email", "Email (optional)", "email"],
            ["phone", "Phone", "tel"],
            ["gstin", "GSTIN (optional)", "text"],
            ["invoice_prefix", "Invoice prefix", "text"],
          ].map(([key, label, type]) => (
            <label key={key} className="block font-sans text-sm">
              <span className="text-[var(--muted)]">{label}</span>
              <input
                className={inputClass}
                type={type}
                required={!label.includes("optional")}
                value={form[key as keyof typeof form]}
                onChange={setField(key as keyof typeof form)}
              />
            </label>
          ))}
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Address</span>
            <textarea className={`${inputClass} min-h-20 py-2`} value={form.address} onChange={setField("address")} />
          </label>
          {[
            ["password", "Password (min 8 characters)"],
            ["confirm_password", "Confirm password"],
          ].map(([key, label]) => (
            <label key={key} className="block font-sans text-sm">
              <span className="text-[var(--muted)]">{label}</span>
              <input
                className={inputClass}
                type="password"
                minLength={8}
                required
                value={form[key as keyof typeof form]}
                onChange={setField(key as keyof typeof form)}
              />
            </label>
          ))}
          <button
            type="submit"
            disabled={busy}
            className="mt-2 h-11 rounded-md bg-[var(--accent)] font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
          >
            {busy ? "Creating shop…" : "Create shop and sign in"}
          </button>
        </form>
      </section>
    </div>
  );
};
