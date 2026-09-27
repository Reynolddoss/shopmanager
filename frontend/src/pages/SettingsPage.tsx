import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { UI_THEMES, normalizeTheme, useTheme, type UiTheme } from "../context/ThemeProvider.tsx";
import { apiClient } from "../services/api.ts";

type ShopSettings = {
  shop_name: string;
  address: string;
  gstin: string;
  phone: string;
  invoice_prefix: string;
  backup_retention_count: number;
  scheduled_backup_enabled: boolean;
  ui_theme: UiTheme;
  extra: Record<string, string>;
};

type BackupRow = { folder: string; created_at?: string; reason?: string };

export const SettingsPage = () => {
  const { theme, setTheme } = useTheme();
  const [settings, setSettings] = useState<ShopSettings | null>(null);
  const [backups, setBackups] = useState<BackupRow[]>([]);
  const [message, setMessage] = useState("");
  const [confirmFolder, setConfirmFolder] = useState("");

  const load = () => {
    void apiClient.get<ShopSettings>("/settings/").then((row) => {
      const next = { ...row, ui_theme: normalizeTheme(row.ui_theme) };
      setSettings(next);
      setTheme(next.ui_theme);
    });
    void apiClient.get<{ results: BackupRow[] }>("/backups/").then((payload) => setBackups(payload.results));
  };

  useEffect(() => {
    load();
  }, []);

  if (!settings) {
    return <p className="font-sans text-sm text-[var(--muted)]">Loading settings…</p>;
  }

  const save = () => {
    void apiClient.patch<ShopSettings>("/settings/", settings).then((row) => {
      const next = { ...row, ui_theme: normalizeTheme(row.ui_theme) };
      setSettings(next);
      setTheme(next.ui_theme);
      setMessage("Settings saved.");
    });
  };

  const pickTheme = (ui_theme: UiTheme) => {
    setSettings({ ...settings, ui_theme });
    setTheme(ui_theme);
  };

  return (
    <section>
      <h2 className="text-3xl">Settings</h2>
      <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
        Shop identity, appearance, backup schedule, and restore. The live database is never stored inside the installer
        folder. Brands and categories live under{" "}
        <Link to="/catalog" className="text-[var(--accent)] underline-offset-2 hover:underline">
          Catalog
        </Link>
        .
      </p>
      {message ? <p className="mt-3 font-sans text-sm">{message}</p> : null}

      <div className="mt-8">
        <h3 className="text-xl">Appearance</h3>
        <p className="mt-1 font-sans text-sm text-[var(--muted)]">
          Choose a theme for this shop. Preview applies immediately; save to keep it for every operator on this install.
        </p>
        <div className="mt-4 grid max-w-2xl gap-3">
          {UI_THEMES.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => pickTheme(option.id)}
              className={[
                "rounded-xl border p-4 text-left font-sans transition-colors",
                (settings.ui_theme || theme) === option.id
                  ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                  : "border-[var(--line)] bg-[var(--panel)] hover:border-[var(--accent)]",
              ].join(" ")}
            >
              <span className="block text-sm font-medium text-[var(--ink)]">{option.label}</span>
              <span className="mt-1 block text-sm text-[var(--muted)]">{option.blurb}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-10 grid max-w-xl gap-3">
        <h3 className="text-xl">Shop identity</h3>
        {["shop_name", "gstin", "phone", "invoice_prefix", "address"].map((key) => (
          <label key={key} className="block font-sans text-sm">
            <span className="text-[var(--muted)]">{key}</span>
            <input
              className="mt-1 h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3"
              value={String(settings[key as keyof ShopSettings] ?? "")}
              onChange={(event) => setSettings({ ...settings, [key]: event.target.value })}
            />
          </label>
        ))}
        <label className="flex items-center gap-2 font-sans text-sm">
          <input
            type="checkbox"
            checked={settings.scheduled_backup_enabled}
            onChange={(event) => setSettings({ ...settings, scheduled_backup_enabled: event.target.checked })}
          />
          Daily backup when the app is running
        </label>
        <button
          type="button"
          className="h-10 rounded-md bg-[var(--accent)] px-3 font-sans text-sm text-[var(--on-accent)]"
          onClick={save}
        >
          Save settings
        </button>
      </div>
      <div className="mt-10">
        <h3 className="text-xl">Backups</h3>
        <button
          type="button"
          className="mt-3 h-10 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
          onClick={() => {
            void apiClient.post("/backups/", { reason: "manual" }).then(() => {
              setMessage("Backup created and validated.");
              load();
            });
          }}
        >
          Backup now
        </button>
        <ul className="mt-4 space-y-2 font-sans text-sm">
          {backups.map((row) => (
            <li key={row.folder} className="flex items-center justify-between gap-3 border-b border-[var(--line)] py-2">
              <span>
                {row.folder} · {row.reason || ""}
              </span>
              <button
                type="button"
                className="rounded border border-[var(--line)] px-2 py-1"
                onClick={() => setConfirmFolder(row.folder)}
              >
                Restore
              </button>
            </li>
          ))}
        </ul>
        {confirmFolder ? (
          <div className="mt-4 rounded-md border border-[var(--line)] bg-[var(--panel)] p-4 font-sans text-sm">
            <p>Restore {confirmFolder}? A safety copy of the current shop file is taken first.</p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="rounded-md bg-[var(--accent)] px-3 py-2 text-[var(--on-accent)]"
                onClick={() => {
                  void apiClient.post("/backups/restore/", { folder: confirmFolder, confirm: true }).then(() => {
                    setMessage("Restore finished. Restart the app if totals look stale.");
                    setConfirmFolder("");
                    load();
                  });
                }}
              >
                Confirm restore
              </button>
              <button
                type="button"
                className="rounded-md border border-[var(--line)] px-3 py-2"
                onClick={() => setConfirmFolder("")}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
};
