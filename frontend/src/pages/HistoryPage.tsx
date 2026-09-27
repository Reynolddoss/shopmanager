import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient, type Paginated } from "../services/api.ts";
import { formatMoney } from "../utils/money.ts";
import { printHtmlDocument } from "../utils/printHtml.ts";

type HistoryTab = "bills" | "purchases";

type SaleRow = {
  id: number;
  invoice_number: string;
  invoice_date: string;
  customer_name: string | null;
  grand_total: string;
  amount_paid: string;
  amount_due: string;
  payment_method: string;
  payment_status: string;
  item_count: number;
  is_cancelled: boolean;
};

type PurchaseRow = {
  id: number;
  bill_number: string;
  bill_date: string;
  vendor_name: string;
  grand_total: string;
  amount_paid: string;
  payment_method: string;
  item_count: number;
  is_cancelled: boolean;
};

type InvoiceItem = {
  name?: string;
  specification?: string;
  quantity?: string;
  unit_price?: string;
  discount?: string;
  line_total?: string;
};

type InvoicePayload = {
  invoice_number: string;
  invoice_date: string;
  customer: string;
  items: InvoiceItem[];
  subtotal: string;
  discount_amount: string;
  gst_amount: string;
  grand_total: string;
  amount_paid: string;
  amount_due: string;
  amount_tendered?: string;
  change_given?: string;
  payment_method?: string;
  payment_reference?: string;
};

type PurchaseDetail = {
  bill_number: string;
  bill_date: string;
  vendor_name: string;
  grand_total: string;
  amount_paid: string;
  payment_method: string;
  gst_amount: string;
  subtotal: string;
  items: {
    product: number;
    quantity: string;
    effective_purchase_cost: string;
    line_total: string;
  }[];
};

const fieldClass = "h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm";

const todayIso = () => new Date().toISOString().slice(0, 10);
const monthStartIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
};

/**
 * Browse past sales bills and purchase bills — search, filter by date, open & print.
 */
export const HistoryPage = () => {
  const [tab, setTab] = useState<HistoryTab>("bills");
  const [query, setQuery] = useState("");
  const [dateFrom, setDateFrom] = useState(monthStartIso);
  const [dateTo, setDateTo] = useState(todayIso);
  const [sales, setSales] = useState<SaleRow[]>([]);
  const [purchases, setPurchases] = useState<PurchaseRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedSaleId, setSelectedSaleId] = useState<number | null>(null);
  const [invoice, setInvoice] = useState<InvoicePayload | null>(null);
  const [selectedPurchase, setSelectedPurchase] = useState<PurchaseDetail | null>(null);

  const load = () => {
    setBusy(true);
    setError("");
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (query.trim()) params.set("search", query.trim());
    const qs = params.toString();
    if (tab === "bills") {
      void apiClient
        .get<Paginated<SaleRow>>(`/sales/?${qs}`)
        .then((page) => setSales(page.results))
        .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load bills"))
        .finally(() => setBusy(false));
    } else {
      void apiClient
        .get<Paginated<PurchaseRow>>(`/purchases/?${qs}`)
        .then((page) => setPurchases(page.results))
        .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load purchases"))
        .finally(() => setBusy(false));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when tab/dates change; search is manual
  }, [tab, dateFrom, dateTo]);

  const openSale = (id: number) => {
    setSelectedSaleId(id);
    setSelectedPurchase(null);
    setInvoice(null);
    void apiClient
      .get<InvoicePayload>(`/sales/${id}/invoice/`)
      .then(setInvoice)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not open invoice"));
  };

  const openPurchase = (id: number) => {
    setSelectedSaleId(null);
    setInvoice(null);
    void apiClient
      .get<PurchaseDetail>(`/purchases/${id}/`)
      .then(setSelectedPurchase)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not open purchase"));
  };

  const printSale = () => {
    if (!selectedSaleId) return;
    void apiClient
      .get<{ html: string }>(`/sales/${selectedSaleId}/print/?kind=a4`)
      .then((payload) => printHtmlDocument(payload.html))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not print invoice"));
  };

  return (
    <section className="w-full">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl">History</h2>
          <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
            Browse past sale bills and supplier bills. Open a row to see lines, payment, and print a sale invoice.
          </p>
        </div>
        <Link to="/sales" className="font-sans text-sm text-[var(--accent)] no-underline hover:underline">
          New bill →
        </Link>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {(
          [
            ["bills", "Sale bills"],
            ["purchases", "Supplier bills"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "bg-[var(--accent)] text-[var(--on-accent)]" : ""}
            onClick={() => {
              setTab(id);
              setInvoice(null);
              setSelectedPurchase(null);
              setSelectedSaleId(null);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <form
        className="mt-4 grid gap-3 sm:grid-cols-[1fr_9rem_9rem_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
      >
        <input
          className={fieldClass}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={tab === "bills" ? "Search invoice, customer, phone, UPI ref…" : "Search bill no. or vendor…"}
        />
        <input className={fieldClass} type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input className={fieldClass} type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <button type="submit" className="bg-[var(--accent)] text-[var(--on-accent)]" disabled={busy}>
          {busy ? "Loading…" : "Search"}
        </button>
      </form>

      {error ? <p className="mt-3 font-sans text-sm text-[var(--danger)]">{error}</p> : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="overflow-x-auto rounded-xl border border-[var(--line)] bg-[var(--panel)]">
          {tab === "bills" ? (
            <table className="w-full min-w-[40rem] font-sans text-sm">
              <thead>
                <tr className="text-left text-[var(--muted)]">
                  <th className="px-3 py-2">Invoice</th>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Customer</th>
                  <th className="px-3 py-2">Total</th>
                  <th className="px-3 py-2">Paid</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {sales.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-8 text-[var(--muted)]">
                      No sale bills in this range.
                    </td>
                  </tr>
                ) : (
                  sales.map((row) => (
                    <tr
                      key={row.id}
                      className={[
                        "cursor-pointer border-t border-[var(--line)]",
                        selectedSaleId === row.id ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--paper)]",
                      ].join(" ")}
                      onClick={() => openSale(row.id)}
                    >
                      <td className="px-3 py-2 font-medium">
                        {row.invoice_number}
                        {row.is_cancelled ? (
                          <span className="ml-2 text-xs text-[var(--danger)]">cancelled</span>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">{row.invoice_date}</td>
                      <td className="px-3 py-2">{row.customer_name || "Walk-in"}</td>
                      <td className="money money-total px-3 py-2">₹{formatMoney(row.grand_total)}</td>
                      <td className="money money-paid px-3 py-2">
                        ₹{formatMoney(row.amount_paid)}
                        <span className="mt-0.5 block text-[11px] font-normal text-[var(--muted)]">{row.payment_method}</span>
                      </td>
                      <td className="px-3 py-2">
                        {row.payment_status}
                        <span className="mt-0.5 block text-[11px] text-[var(--muted)]">{row.item_count} lines</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          ) : (
            <table className="w-full min-w-[36rem] font-sans text-sm">
              <thead>
                <tr className="text-left text-[var(--muted)]">
                  <th className="px-3 py-2">Bill</th>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Vendor</th>
                  <th className="px-3 py-2">Total</th>
                  <th className="px-3 py-2">Paid</th>
                </tr>
              </thead>
              <tbody>
                {purchases.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-[var(--muted)]">
                      No purchases in this range.
                    </td>
                  </tr>
                ) : (
                  purchases.map((row) => (
                    <tr
                      key={row.id}
                      className={[
                        "cursor-pointer border-t border-[var(--line)]",
                        selectedPurchase?.bill_number === row.bill_number
                          ? "bg-[var(--accent-soft)]"
                          : "hover:bg-[var(--paper)]",
                      ].join(" ")}
                      onClick={() => openPurchase(row.id)}
                    >
                      <td className="px-3 py-2 font-medium">{row.bill_number}</td>
                      <td className="px-3 py-2">{row.bill_date}</td>
                      <td className="px-3 py-2">{row.vendor_name}</td>
                      <td className="money money-total px-3 py-2">₹{formatMoney(row.grand_total)}</td>
                      <td className="money money-paid px-3 py-2">
                        ₹{formatMoney(row.amount_paid)}
                        <span className="mt-0.5 block text-[11px] font-normal text-[var(--muted)]">{row.payment_method}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>

        <aside className="h-fit rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[var(--shadow)] xl:sticky xl:top-4">
          <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Details</p>
          {invoice ? (
            <div className="mt-2 font-sans text-sm">
              <h3 className="text-xl">{invoice.invoice_number}</h3>
              <p className="mt-1 text-[var(--muted)]">
                {invoice.customer} · {invoice.invoice_date}
              </p>
              <ul className="mt-4 max-h-64 space-y-2 overflow-y-auto border-t border-[var(--line)] pt-3">
                {invoice.items.map((item, index) => (
                  <li key={index} className="flex justify-between gap-2">
                    <span>
                      <span className="block">{item.name}</span>
                      {item.specification ? (
                        <span className="block text-[11px] text-[var(--muted)]">{item.specification}</span>
                      ) : null}
                      <span className="block text-[11px] text-[var(--muted)]">
                        {formatMoney(item.quantity)} × ₹{formatMoney(item.unit_price)}
                      </span>
                    </span>
                    <span className="money money-line shrink-0">₹{formatMoney(item.line_total)}</span>
                  </li>
                ))}
              </ul>
              <dl className="mt-4 space-y-2 border-t border-[var(--line)] pt-3">
                {Number(invoice.discount_amount ?? 0) > 0 || Number(invoice.subtotal ?? 0) > 0 ? (
                  <>
                    <div className="flex justify-between gap-3">
                      <dt className="text-[var(--muted)]">Subtotal</dt>
                      <dd className="money money-subtotal">₹{formatMoney(invoice.subtotal)}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt
                        className={
                          Number(invoice.discount_amount) > 0
                            ? "font-semibold text-[var(--discount)]"
                            : "text-[var(--muted)]"
                        }
                      >
                        Discount
                      </dt>
                      <dd
                        className={
                          Number(invoice.discount_amount) > 0 ? "money money-discount" : "money money-discount-zero"
                        }
                      >
                        −₹{formatMoney(invoice.discount_amount)}
                      </dd>
                    </div>
                  </>
                ) : null}
                <div className="money-bill-row flex justify-between gap-3">
                  <dt className="font-bold">Total</dt>
                  <dd className="money money-total">₹{formatMoney(invoice.grand_total)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Paid</dt>
                  <dd className="money money-paid">₹{formatMoney(invoice.amount_paid)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className={Number(invoice.amount_due) > 0 ? "font-semibold text-[var(--danger)]" : "text-[var(--muted)]"}>
                    Due
                  </dt>
                  <dd className={Number(invoice.amount_due) > 0 ? "money money-due" : "money money-due-clear"}>
                    ₹{formatMoney(invoice.amount_due)}
                  </dd>
                </div>
                {Number(invoice.amount_tendered ?? 0) > 0 && invoice.payment_method === "CASH" ? (
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--muted)]">Cash · Change</dt>
                    <dd>
                      <span className="money money-subtotal">₹{formatMoney(invoice.amount_tendered)}</span>
                      <span className="text-[var(--muted)]"> · </span>
                      <span className="money money-change">₹{formatMoney(invoice.change_given)}</span>
                    </dd>
                  </div>
                ) : null}
                {invoice.payment_reference ? (
                  <div className="flex justify-between gap-2">
                    <dt className="text-[var(--muted)]">Ref</dt>
                    <dd className="text-right break-all">{invoice.payment_reference}</dd>
                  </div>
                ) : null}
              </dl>
              <button type="button" className="mt-4 w-full bg-[var(--accent)] text-[var(--on-accent)]" onClick={printSale}>
                Print A4
              </button>
            </div>
          ) : selectedPurchase ? (
            <div className="mt-2 font-sans text-sm">
              <h3 className="text-xl">{selectedPurchase.bill_number}</h3>
              <p className="mt-1 text-[var(--muted)]">
                {selectedPurchase.vendor_name} · {selectedPurchase.bill_date}
              </p>
              <ul className="mt-4 max-h-64 space-y-2 overflow-y-auto border-t border-[var(--line)] pt-3">
                {selectedPurchase.items.map((item, index) => (
                  <li key={index} className="flex justify-between gap-2">
                    <span>
                      Product #{item.product}
                      <span className="mt-0.5 block text-[11px] text-[var(--muted)]">
                        {formatMoney(item.quantity)} × ₹{formatMoney(item.effective_purchase_cost)}
                      </span>
                    </span>
                    <span className="money money-line">₹{formatMoney(item.line_total)}</span>
                  </li>
                ))}
              </ul>
              <dl className="mt-4 space-y-2 border-t border-[var(--line)] pt-3">
                <div className="flex justify-between gap-3">
                  <dt className="font-bold">Total</dt>
                  <dd className="money money-total">₹{formatMoney(selectedPurchase.grand_total)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Paid</dt>
                  <dd className="money money-paid">
                    ₹{formatMoney(selectedPurchase.amount_paid)}
                    <span className="ml-1 font-sans text-xs font-normal text-[var(--muted)]">
                      ({selectedPurchase.payment_method})
                    </span>
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="mt-3 font-sans text-sm text-[var(--muted)]">Select a row to see full details.</p>
          )}
        </aside>
      </div>
    </section>
  );
};
