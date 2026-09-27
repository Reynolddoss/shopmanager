import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useToast } from "../hooks/useToast.ts";
import { apiClient, type FinderRow, type Paginated } from "../services/api.ts";
import { formatMoney, sanitizeDecimalInput } from "../utils/money.ts";

type Vendor = { id: number; name: string };

/**
 * One line on a supplier bill — same lot pricing as Add stock, plus vendor ledger.
 */
type Line = {
  product_id: number;
  sku: string;
  name: string;
  quantity: string;
  base_purchase_price: string;
  supplier_discount_percent: string;
  mrp: string;
  selling_price: string;
  safe_selling_price: string;
  maximum_discount_percent: string;
  pricing_confirmed: boolean;
};

const fieldClass = "h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm";
const moneyOrZero = (value: string | null | undefined) => formatMoney(value ?? "0");

/**
 * Supplier bills — use when a vendor invoice must hit payables.
 * For opening stock / cash top-ups with no bill, use product → Add stock instead.
 */
export const PurchasesPage = () => {
  const { push } = useToast();
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [vendorId, setVendorId] = useState("");
  const [vendorInvoice, setVendorInvoice] = useState("");
  const [amountPaid, setAmountPaid] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("CASH");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<FinderRow[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void apiClient.get<Paginated<Vendor>>("/vendors/").then((page) => setVendors(page.results));
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void apiClient
        .get<Paginated<FinderRow>>(`/products/finder/?q=${encodeURIComponent(query)}`)
        .then((page) => setHits(page.results));
    }, 120);
    return () => window.clearTimeout(handle);
  }, [query]);

  const updateLine = (index: number, patch: Partial<Line>) => {
    setLines((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const addHit = (hit: FinderRow) => {
    setLines((current) => [
      ...current,
      {
        product_id: hit.id,
        sku: hit.sku,
        name: hit.name,
        quantity: "1.00",
        base_purchase_price: moneyOrZero(hit.last_purchase_price ?? hit.active_cost),
        supplier_discount_percent: "0.00",
        mrp: moneyOrZero(hit.active_mrp),
        selling_price: moneyOrZero(hit.active_selling_price),
        safe_selling_price: moneyOrZero(hit.active_safe_selling_price),
        maximum_discount_percent: moneyOrZero(hit.active_max_discount),
        pricing_confirmed: true,
      },
    ]);
    setQuery("");
    setHits([]);
  };

  const post = () => {
    if (!vendorId) {
      push("error", "Vendor needed", "Pick the supplier for this bill.");
      return;
    }
    if (!lines.length) {
      push("error", "No items", "Add at least one product line.");
      return;
    }
    setBusy(true);
    void apiClient
      .post("/purchases/", {
        vendor_id: Number(vendorId),
        vendor_invoice_number: vendorInvoice.trim(),
        amount_paid: amountPaid || "0",
        payment_method: paymentMethod,
        items: lines.map((line) => ({
          product_id: line.product_id,
          quantity: line.quantity,
          base_purchase_price: line.base_purchase_price,
          supplier_discount_percent: line.supplier_discount_percent,
          mrp: line.mrp,
          selling_price: line.selling_price,
          safe_selling_price: line.safe_selling_price,
          maximum_discount_percent: line.maximum_discount_percent,
          pricing_confirmed: true,
          pricing_mode: "NEW",
        })),
      })
      .then(() => {
        setLines([]);
        setVendorInvoice("");
        setAmountPaid("");
        push("success", "Supplier bill posted", "Stock lots created and vendor ledger updated.");
      })
      .catch((error: unknown) =>
        push("error", "Not posted", error instanceof Error ? error.message : "Request failed."),
      )
      .finally(() => setBusy(false));
  };

  return (
    <section className="w-full max-w-5xl">
      <h2 className="text-3xl">Supplier bills</h2>
      <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
        Use this when a supplier gives you an invoice you need on the books (what you owe them). It adds stock{" "}
        <em>and</em> updates the vendor payable.
      </p>
      <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 font-sans text-sm">
        <p className="font-medium">When to use which</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--ink)]">Add stock</strong> on a product — opening stock or a quick top-up with{" "}
            <em>no</em> supplier bill to track.
          </li>
          <li>
            <strong className="text-[var(--ink)]">Supplier bills</strong> (this page) — vendor invoice, payables, purchase
            history.
          </li>
        </ul>
        <p className="mt-2 text-xs text-[var(--muted)]">
          Need only stock? Open{" "}
          <Link to="/inventory" className="text-[var(--accent)] underline-offset-2 hover:underline">
            Inventory
          </Link>
          , pick a product, then <strong className="text-[var(--ink)]">Add stock</strong>.
        </p>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <label className="block font-sans text-sm">
          <span className="text-xs text-[var(--muted)]">Supplier</span>
          <select className={`${fieldClass} mt-1`} value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
            <option value="">Select vendor</option>
            {vendors.map((vendor) => (
              <option key={vendor.id} value={vendor.id}>
                {vendor.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block font-sans text-sm">
          <span className="text-xs text-[var(--muted)]">Their invoice # (optional)</span>
          <input
            className={`${fieldClass} mt-1`}
            value={vendorInvoice}
            onChange={(e) => setVendorInvoice(e.target.value)}
            placeholder="As printed on supplier bill"
          />
        </label>
      </div>

      <label className="mt-4 block font-sans text-sm">
        <span className="text-xs text-[var(--muted)]">Add product</span>
        <input
          className={`${fieldClass} mt-1`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, SKU…"
        />
      </label>
      {hits.length ? (
        <ul className="mt-2 max-h-40 overflow-y-auto rounded-md border border-[var(--line)]">
          {hits.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                className="flex w-full justify-between rounded-none border-0 border-b border-[var(--line)] px-3 py-2 text-left shadow-none last:border-b-0"
                onClick={() => addHit(hit)}
              >
                <span>
                  {hit.name}
                  <span className="mt-0.5 block text-xs text-[var(--muted)]">{hit.sku}</span>
                </span>
                <span className="text-xs text-[var(--muted)]">Add</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-6 space-y-4">
        {lines.length === 0 ? (
          <p className="font-sans text-sm text-[var(--muted)]">No lines yet — search and add products from this bill.</p>
        ) : (
          lines.map((line, index) => {
            const qty = Number(line.quantity) || 0;
            const price = Number(line.base_purchase_price) || 0;
            const disc = Number(line.supplier_discount_percent) || 0;
            const unitCost = price * (1 - disc / 100);
            const lotTotal = qty * unitCost;
            return (
              <div key={`${line.product_id}-${index}`} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{line.name}</p>
                    <p className="text-xs text-[var(--muted)]">{line.sku}</p>
                  </div>
                  <button type="button" onClick={() => setLines((rows) => rows.filter((_, i) => i !== index))}>
                    Remove
                  </button>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 font-sans text-sm">
                  {(
                    [
                      ["quantity", "Qty"],
                      ["base_purchase_price", "Purchase ₹ / unit"],
                      ["supplier_discount_percent", "Supplier disc %"],
                      ["mrp", "MRP / unit"],
                      ["selling_price", "Selling ₹ / unit"],
                      ["safe_selling_price", "Safe ₹ / unit"],
                      ["maximum_discount_percent", "Max cust. disc %"],
                    ] as const
                  ).map(([key, label]) => (
                    <label key={key} className="block">
                      <span className="text-xs text-[var(--muted)]">{label}</span>
                      <input
                        className={`${fieldClass} mt-1`}
                        value={line[key]}
                        onChange={(e) => updateLine(index, { [key]: sanitizeDecimalInput(e.target.value, 2) })}
                      />
                    </label>
                  ))}
                </div>
                <p className="mt-2 font-sans text-xs text-[var(--muted)]">
                  Lot total ≈ ₹{formatMoney(lotTotal)} ({formatMoney(qty)} × ₹{formatMoney(unitCost)} after supplier
                  discount)
                </p>
              </div>
            );
          })
        )}
      </div>

      {lines.length ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <label className="block font-sans text-sm">
            <span className="text-xs text-[var(--muted)]">Paid to supplier now (₹)</span>
            <input
              className={`${fieldClass} mt-1`}
              value={amountPaid}
              onChange={(e) => setAmountPaid(sanitizeDecimalInput(e.target.value, 2))}
              placeholder="0 if credit / pay later"
            />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-xs text-[var(--muted)]">Payment method</span>
            <select className={`${fieldClass} mt-1`} value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
              {["CASH", "UPI", "CARD", "BANK", "CREDIT"].map((method) => (
                <option key={method} value={method}>
                  {method}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      <button
        type="button"
        className="mt-6 bg-[var(--accent)] text-[var(--on-accent)]"
        disabled={busy || !lines.length}
        onClick={post}
      >
        {busy ? "Posting…" : "Post supplier bill"}
      </button>
    </section>
  );
};
