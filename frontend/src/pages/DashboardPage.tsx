import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../services/api.ts";
import { HOME_TILES, NavIcon } from "../navigation.tsx";
import { formatMoney } from "../utils/money.ts";

type Dashboard = {
  today_sales: string;
  today_profit: string;
  today_purchases: string;
  today_invoices: number;
  receivables: string;
  payables: string;
  stock_value: string;
  low_stock_count: number;
  top_products: { sku: string; name: string; revenue: string }[];
  recent_sales: { invoice_number: string; customer: string; total: string }[];
  insights: { code: string; message: string }[];
};

const Stat = ({ label, value, hint }: { label: string; value: string; hint?: string }) => (
  <article className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-5 shadow-[var(--shadow)]">
    <p className="font-sans text-xs tracking-wide text-[var(--muted)] uppercase">{label}</p>
    <p className="mt-2 text-2xl">{value}</p>
    {hint ? <p className="mt-1 font-sans text-xs text-[var(--muted)]">{hint}</p> : null}
  </article>
);

/**
 * Home launchpad: large icon tiles for one-tap access, then today’s summary below.
 */
export const DashboardPage = () => {
  const [data, setData] = useState<Dashboard | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void apiClient
      .get<Dashboard>("/analytics/dashboard/")
      .then(setData)
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Dashboard unavailable."));
  }, []);

  return (
    <section className="w-full">
      <div>
        <h2 className="text-3xl">Home</h2>
        <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
          Tap an icon to open that screen. Sidebar groups the same places for when you are already deep in a task.
        </p>
      </div>

      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {HOME_TILES.map((tile) => (
          <Link
            key={tile.to}
            to={tile.to}
            className="group flex flex-col items-start gap-3 rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-5 shadow-[var(--shadow)] no-underline transition-[border-color,transform] duration-150 hover:border-[var(--accent)] hover:translate-y-[-1px]"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
              <NavIcon id={tile.icon} className="h-6 w-6" />
            </span>
            <span>
              <span className="block text-lg leading-tight text-[var(--ink)]">{tile.label}</span>
              {tile.blurb ? (
                <span className="mt-1 block font-sans text-xs leading-snug text-[var(--muted)]">{tile.blurb}</span>
              ) : null}
            </span>
          </Link>
        ))}
      </div>

      <div className="mt-10">
        <h3 className="text-xl">Today</h3>
        <p className="mt-1 font-sans text-sm text-[var(--muted)]">
          Numbers from posted sales, purchases, lots, and ledgers.
        </p>
      </div>
      {message ? <p className="mt-4 font-sans text-sm text-[var(--danger)]">{message}</p> : null}
      {data ? (
        <>
          <div className="mt-4 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            <Stat label="Sales" value={`₹${formatMoney(data.today_sales)}`} hint={`${data.today_invoices} invoices`} />
            <Stat label="Profit" value={`₹${formatMoney(data.today_profit)}`} />
            <Stat label="Purchases" value={`₹${formatMoney(data.today_purchases)}`} />
            <Stat label="Stock value" value={`₹${formatMoney(data.stock_value)}`} hint={`${data.low_stock_count} low`} />
            <Stat label="Receivables" value={`₹${formatMoney(data.receivables)}`} />
            <Stat label="Payables" value={`₹${formatMoney(data.payables)}`} />
          </div>
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <article className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-5">
              <h3 className="text-lg">Insights</h3>
              <ul className="mt-3 space-y-2 font-sans text-sm">
                {(data.insights.length ? data.insights : [{ code: "NONE", message: "No alerts from current data." }]).map(
                  (item) => (
                    <li key={item.code + item.message}>{item.message}</li>
                  ),
                )}
              </ul>
            </article>
            <article className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-5">
              <h3 className="text-lg">Top products today</h3>
              <ul className="mt-3 space-y-2 font-sans text-sm">
                {(data.top_products.length
                  ? data.top_products
                  : [{ sku: "—", name: "No sales today", revenue: "0.00" }]
                ).map((item) => (
                  <li key={item.sku} className="flex justify-between gap-3">
                    <span>
                      {item.sku} · {item.name}
                    </span>
                    <span>₹{formatMoney(item.revenue)}</span>
                  </li>
                ))}
              </ul>
            </article>
            <article className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-5 lg:col-span-2">
              <h3 className="text-lg">Recent sales</h3>
              <ul className="mt-3 space-y-2 font-sans text-sm">
                {data.recent_sales.length ? (
                  data.recent_sales.map((sale) => (
                    <li key={sale.invoice_number} className="flex justify-between gap-3">
                      <span>
                        {sale.invoice_number} · {sale.customer}
                      </span>
                      <span>₹{formatMoney(sale.total)}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-[var(--muted)]">No sales yet today.</li>
                )}
              </ul>
            </article>
          </div>
        </>
      ) : null}
    </section>
  );
};
