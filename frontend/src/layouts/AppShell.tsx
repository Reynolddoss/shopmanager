import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { SmartFinder } from "../components/SmartFinder.tsx";
import { ToastViewport } from "../components/ToastViewport.tsx";
import { useAuth } from "../context/AuthProvider.tsx";
import { useBackendStatus } from "../hooks/useBackendStatus.ts";
import { useToast } from "../hooks/useToast.ts";
import { NAV_GROUPS, NavIcon } from "../navigation.tsx";

export const AppShell = () => {
  const { status, logout } = useAuth();
  const { state, health, version, message } = useBackendStatus();
  const { push } = useToast();
  const [finderQuery, setFinderQuery] = useState("");
  const shopName = status?.shop?.name || "Shop Manager";
  const operatorName = status?.user?.full_name || status?.user?.username || "Owner";

  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[var(--line)] bg-[var(--panel)]">
        <div className="border-b border-[var(--line)] px-5 py-5">
          <p className="text-[11px] tracking-[0.2em] text-[var(--muted)] uppercase">Shop manager</p>
          <h1 className="mt-1 text-2xl leading-none">{shopName}</h1>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.id} className="mb-3">
              <p className="px-3 pb-1 text-[10px] tracking-[0.16em] text-[var(--muted)] uppercase">{group.label}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    [
                      "mb-0.5 flex items-center gap-2.5 rounded-md px-3 py-2 font-sans text-sm",
                      isActive
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "text-[var(--ink)] hover:bg-[var(--paper)]",
                    ].join(" ")
                  }
                >
                  <NavIcon id={item.icon} className="h-4 w-4 shrink-0 opacity-90" />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-4 border-b border-[var(--line)] bg-[var(--panel)] px-6 py-3">
          <SmartFinder query={finderQuery} onQueryChange={setFinderQuery} />
          <button
            type="button"
            className="h-9 rounded-md border border-[var(--line)] px-3 font-sans text-sm"
            onClick={() =>
              push("info", "Notifications", "No alerts yet. This tray will hold stock and backup notices.")
            }
          >
            Alerts
          </button>
          <div className="font-sans text-xs text-[var(--muted)]">
            {state === "ready"
              ? `${version?.name} ${version?.version}`
              : state === "loading"
                ? "Connecting…"
                : "API offline"}
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto p-8">
          {health?.recovery_message ? (
            <p
              className="mb-4 rounded-md border p-3 font-sans text-sm"
              style={{
                borderColor: "var(--warn-line)",
                background: "var(--warn-bg)",
                color: "var(--warn-ink)",
              }}
            >
              {health.recovery_message}
            </p>
          ) : null}
          <Outlet />
        </main>
        <footer className="flex items-center justify-between border-t border-[var(--line)] bg-[var(--panel)] px-6 py-2 font-sans text-xs text-[var(--muted)]">
          <span>
            {state === "ready"
              ? `SQLite ${health?.journal_mode ?? ""} · integrity ${health?.integrity_check}`
              : message || "Waiting for Django on :8000"}
          </span>
          <div className="flex items-center gap-3">
            <span>{operatorName}</span>
            <button
              type="button"
              className="underline-offset-2 hover:underline"
              onClick={() => {
                void logout().then(() => push("info", "Signed out", "Sign in again to continue working."));
              }}
            >
              Sign out
            </button>
          </div>
        </footer>
      </div>
      <ToastViewport />
    </div>
  );
};
