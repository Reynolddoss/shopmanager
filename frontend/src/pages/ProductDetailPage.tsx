import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ProductImageField } from "../components/ProductImageField.tsx";
import { ErrorState, LoadingState } from "../components/States.tsx";
import { useToast } from "../hooks/useToast.ts";
import { apiClient, type Paginated, type PreviousBatchPayload, type ProductCard } from "../services/api.ts";
import { formatMoney, sanitizeDecimalInput } from "../utils/money.ts";

type DetailTab = "overview" | "stock" | "vendors" | "batches" | "prices" | "receive";

const MONEY_KEYS = new Set([
  "list_purchase_price",
  "supplier_discount_percent",
  "selling_price",
  "safe_selling_price",
  "maximum_discount_percent",
  "mrp",
  "quantity",
  "adjust_qty",
]);

const isDetailTab = (value: string | null): value is DetailTab =>
  value === "overview" ||
  value === "stock" ||
  value === "vendors" ||
  value === "batches" ||
  value === "prices" ||
  value === "receive";

export const ProductDetailPage = () => {
  const { productId } = useParams();
  const [searchParams] = useSearchParams();
  const { push } = useToast();
  const [card, setCard] = useState<ProductCard | null>(null);
  const [tab, setTab] = useState<DetailTab>(() => {
    const fromQuery = searchParams.get("tab");
    return isDetailTab(fromQuery) ? fromQuery : "overview";
  });
  const [priceHistory, setPriceHistory] = useState<{
    history: { date: string; vendor: string; cost: string; absolute_change: string; percent_change: string; lot_code: string }[];
  } | null>(null);
  const [error, setError] = useState("");
  const [previous, setPrevious] = useState<PreviousBatchPayload | null>(null);
  const [vendors, setVendors] = useState<{ id: number; name: string }[]>([]);
  const [form, setForm] = useState({
    quantity: "1",
    list_purchase_price: "",
    supplier_discount_percent: "0",
    selling_price: "",
    safe_selling_price: "",
    maximum_discount_percent: "0",
    mrp: "",
    pricing_mode: "NEW",
    pricing_confirmed: false,
    vendor_id: "",
    reason: "",
    adjust_qty: "1",
    movement_type: "ADJUSTMENT_IN",
  });

  const load = () => {
    if (!productId) {
      return;
    }
    void apiClient
      .get<ProductCard>(`/products/${productId}/card/`)
      .then(setCard)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load product."));
  };

  useEffect(() => {
    load();
    if (productId) {
      void apiClient
        .get<{ history: { date: string; vendor: string; cost: string; absolute_change: string; percent_change: string; lot_code: string }[] }>(
          `/analytics/products/${productId}/price-history/`,
        )
        .then(setPriceHistory);
    }
    void apiClient.get<Paginated<{ id: number; name: string }>>("/vendors/").then((page) => setVendors(page.results));
  }, [productId]);

  useEffect(() => {
    if (!productId || !form.list_purchase_price) {
      return;
    }
    void apiClient
      .get<PreviousBatchPayload>(`/batches/previous/?product=${productId}&new_cost=${form.list_purchase_price}`)
      .then(setPrevious);
  }, [productId, form.list_purchase_price]);

  if (error) {
    return <ErrorState message={error} />;
  }
  if (!card) {
    return <LoadingState label="Loading product…" />;
  }

  const setField = (key: string, value: string | boolean) => {
    const priceKeys = new Set(["list_purchase_price", "selling_price", "safe_selling_price", "mrp", "maximum_discount_percent"]);
    if (typeof value === "string" && MONEY_KEYS.has(key)) {
      setForm((current) => ({
        ...current,
        [key]: sanitizeDecimalInput(value, 2),
        ...(priceKeys.has(key) && current.pricing_mode === "PREVIOUS" ? { pricing_mode: "NEW" } : {}),
      }));
      return;
    }
    setForm((current) => ({ ...current, [key]: value }));
  };

  const receiveBatch = () => {
    if (!form.list_purchase_price || !form.selling_price) {
      push("error", "Prices needed", "Enter this lot’s purchase cost and selling price.");
      return;
    }
    void apiClient
      .post(`/batches/receive/`, {
        product: Number(productId),
        vendor: form.vendor_id ? Number(form.vendor_id) : null,
        quantity: form.quantity,
        list_purchase_price: form.list_purchase_price,
        supplier_discount_percent: form.supplier_discount_percent,
        selling_price: form.selling_price || undefined,
        safe_selling_price: form.safe_selling_price || undefined,
        maximum_discount_percent: form.maximum_discount_percent,
        mrp: form.mrp || undefined,
        pricing_mode: form.pricing_mode || "NEW",
        pricing_confirmed: true,
      })
      .then(() => {
        push(
          "success",
          "New lot saved",
          "A separate lot was added. Older lots keep their own vendor, cost, and prices.",
        );
        setTab("batches");
        setForm((current) => ({
          ...current,
          quantity: "1",
          list_purchase_price: "",
          supplier_discount_percent: "0",
          selling_price: "",
          safe_selling_price: "",
          maximum_discount_percent: "0",
          mrp: "",
          pricing_mode: "NEW",
          vendor_id: "",
        }));
        setPrevious(null);
        load();
      })
      .catch((err: unknown) => push("error", "Batch not saved", err instanceof Error ? err.message : "Request failed."));
  };

  const adjustStock = () => {
    const batchId = card.batches[0]?.id;
    if (!batchId) {
      push("error", "No batch", "Receive a lot before adjusting stock.");
      return;
    }
    void apiClient
      .post(`/stock-movements/adjust/`, {
        batch: batchId,
        movement_type: form.movement_type,
        quantity: form.adjust_qty,
        reason: form.reason,
      })
      .then(() => {
        push("success", "Stock moved", "The movement was written with before/after quantities.");
        load();
      })
      .catch((err: unknown) => push("error", "Adjustment failed", err instanceof Error ? err.message : "Request failed."));
  };

  const copyPrevious = () => {
    if (!previous?.previous) {
      return;
    }
    setForm((current) => ({
      ...current,
      selling_price: formatMoney(previous.previous?.selling_price ?? ""),
      safe_selling_price: formatMoney(previous.previous?.safe_selling_price ?? ""),
      maximum_discount_percent: formatMoney(previous.previous?.maximum_discount_percent ?? "0"),
      list_purchase_price: current.list_purchase_price || formatMoney(previous.previous?.purchase_cost ?? ""),
      pricing_mode: "COPY_EDIT",
      pricing_confirmed: true,
    }));
    push(
      "info",
      "Copied as a starting point",
      "Edit cost/selling for this new lot. The old lot is not changed.",
    );
  };

  return (
    <section>
      <p className="font-sans text-xs text-[var(--muted)]">
        <Link to="/inventory" className="hover:underline">
          Inventory
        </Link>
        <span> / {card.product.sku}</span>
      </p>
      <div className="mt-2 flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 flex-wrap items-start gap-4">
          <div className="h-24 w-24 shrink-0 overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--panel)]">
            {card.product.image_url ? (
              <img src={card.product.image_url} alt="" className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center font-sans text-[11px] text-[var(--muted)]">No photo</div>
            )}
          </div>
          <div className="min-w-0">
            <h2 className="text-3xl">{card.product.name}</h2>
            <p className="mt-1 font-sans text-sm text-[var(--muted)]">
              {card.product.specification || "No specification"} · {card.stock.on_hand} on hand · {card.stock.status}
            </p>
          </div>
        </div>
        <button
          type="button"
          className="rounded-md border border-[var(--line)] px-3 py-2 font-sans text-sm"
          onClick={() =>
            push("info", "Add to sale", "Sales billing is Phase 3. The product is ready to be quoted from this card.")
          }
        >
          Add to sale
        </button>
      </div>
      <div className="mt-6 flex gap-2 font-sans text-sm">
        {(["overview", "stock", "vendors", "batches", "prices", "receive"] as const).map((item) => (
          <button
            key={item}
            type="button"
            className={[
              "rounded-md px-3 py-1.5 capitalize",
              tab === item ? "bg-[var(--accent)] text-white" : "border border-[var(--line)] bg-white",
            ].join(" ")}
            onClick={() => setTab(item)}
          >
            {item === "receive" ? "Add stock" : item}
          </button>
        ))}
      </div>
      {tab === "overview" ? (
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="md:col-span-3">
            <ProductImageField
              productId={card.product.id}
              imageUrl={card.product.image_url}
              onUploaded={(imageUrl) =>
                setCard((current) =>
                  current
                    ? { ...current, product: { ...current.product, image_url: imageUrl } }
                    : current,
                )
              }
            />
          </div>
          {[
            ["On hand", formatMoney(card.stock.on_hand)],
            ["Value (FIFO)", `₹${formatMoney(card.stock.on_hand_value)}`],
            [
              "Sell (next lot)",
              card.pricing
                ? `₹${formatMoney(card.pricing.selling_price)}${card.pricing.lot_code ? ` · ${card.pricing.lot_code}` : ""}`
                : "—",
            ],
            ["Safe", card.pricing ? `₹${formatMoney(card.pricing.safe_selling_price)}` : "—"],
            ["Cost (next lot)", card.pricing ? `₹${formatMoney(card.pricing.current_cost)}` : "—"],
            ["Margin", card.pricing ? `${formatMoney(card.pricing.margin_percent)}%` : "—"],
          ].map((pair) => (
            <article key={pair[0]} className="rounded-xl border border-[var(--line)] bg-white p-5">
              <p className="font-sans text-xs tracking-wide text-[var(--muted)] uppercase">{pair[0]}</p>
              <p className="mt-2 text-2xl">{pair[1]}</p>
            </article>
          ))}
          {card.pricing_latest ? (
            <article className="rounded-xl border border-[var(--line)] bg-white p-5 md:col-span-3">
              <p className="font-sans text-xs tracking-wide text-[var(--muted)] uppercase">Newest lot (not sold yet first)</p>
              <p className="mt-2 font-sans text-sm">
                {card.pricing_latest.lot_code || "Latest"} · sell ₹{formatMoney(card.pricing_latest.selling_price)} ·
                cost ₹{formatMoney(card.pricing_latest.current_cost)}
                {card.pricing_latest.mrp ? ` · MRP ₹${formatMoney(card.pricing_latest.mrp)}` : ""}
              </p>
              <p className="mt-1 font-sans text-xs text-[var(--muted)]">
                Billing defaults to the older next lot. Open Batches to see every lot’s prices.
              </p>
            </article>
          ) : null}
        </div>
      ) : null}
      {tab === "stock" ? (
        <div className="mt-6 rounded-xl border border-[var(--line)] bg-white p-5 font-sans text-sm">
          <p>
            Min {card.stock.min_stock_quantity} · Reorder {card.stock.reorder_level} · Max {card.stock.max_stock_quantity}
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <select
              value={form.movement_type}
              onChange={(event) => setField("movement_type", event.target.value)}
              className="h-10 rounded-md border border-[var(--line)] px-3"
            >
              <option value="OPENING_STOCK">Opening stock</option>
              <option value="ADJUSTMENT_IN">Adjustment in</option>
              <option value="ADJUSTMENT_OUT">Adjustment out</option>
              <option value="DAMAGE">Damage</option>
            </select>
            <input
              value={form.adjust_qty}
              onChange={(event) => setField("adjust_qty", event.target.value)}
              className="h-10 rounded-md border border-[var(--line)] px-3"
              placeholder="Quantity"
            />
            <input
              value={form.reason}
              onChange={(event) => setField("reason", event.target.value)}
              className="h-10 rounded-md border border-[var(--line)] px-3"
              placeholder="Reason"
            />
          </div>
          <button type="button" className="mt-4 rounded-md bg-[var(--accent)] px-3 py-2 text-white" onClick={adjustStock}>
            Record movement
          </button>
        </div>
      ) : null}
      {tab === "vendors" ? (
        <div className="mt-6 overflow-hidden rounded-xl border border-[var(--line)] bg-white">
          <table className="w-full font-sans text-sm">
            <thead className="bg-[var(--paper)] text-left text-xs text-[var(--muted)] uppercase">
              <tr>
                <th className="px-4 py-3">Vendor</th>
                <th className="px-4 py-3">Last cost</th>
                <th className="px-4 py-3">Best cost</th>
                <th className="px-4 py-3">Last purchase</th>
              </tr>
            </thead>
            <tbody>
              {card.vendors.map((vendor) => (
                <tr key={vendor.id} className="border-t border-[var(--line)]">
                  <td className="px-4 py-3">
                    {vendor.vendor_name}
                    {vendor.is_preferred ? " · preferred" : ""}
                  </td>
                  <td className="px-4 py-3">{vendor.last_purchase_price ? `₹${formatMoney(vendor.last_purchase_price)}` : "—"}</td>
                  <td className="px-4 py-3">
                    {vendor.lowest_historical_purchase_price ? `₹${formatMoney(vendor.lowest_historical_purchase_price)}` : "—"}
                  </td>
                  <td className="px-4 py-3">{vendor.last_purchase_date || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {tab === "batches" ? (
        <div className="mt-6 overflow-hidden rounded-xl border border-[var(--line)] bg-white">
          <table className="w-full font-sans text-sm">
            <thead className="bg-[var(--paper)] text-left text-xs text-[var(--muted)] uppercase">
              <tr>
                <th className="px-4 py-3">Lot</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Selling</th>
                <th className="px-4 py-3">Safe</th>
                <th className="px-4 py-3">Stock</th>
              </tr>
            </thead>
            <tbody>
              {card.batches.map((batch) => (
                <tr key={batch.id} className="border-t border-[var(--line)]">
                  <td className="px-4 py-3">
                    {batch.lot_code} · {batch.vendor_name || "—"}
                  </td>
                  <td className="px-4 py-3">₹{formatMoney(batch.purchase_cost)}</td>
                  <td className="px-4 py-3">₹{formatMoney(batch.selling_price)}</td>
                  <td className="px-4 py-3">₹{formatMoney(batch.safe_selling_price)}</td>
                  <td className="px-4 py-3">
                    {formatMoney(batch.remaining_quantity)} / {formatMoney(batch.original_quantity)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {tab === "prices" ? (
        <div className="mt-6 overflow-hidden rounded-xl border border-[var(--line)] bg-white">
          <table className="w-full font-sans text-sm">
            <thead className="bg-[var(--paper)] text-left text-xs text-[var(--muted)] uppercase">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Lot</th>
                <th className="px-4 py-3">Vendor</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Change</th>
              </tr>
            </thead>
            <tbody>
              {(priceHistory?.history || []).map((row) => (
                <tr key={row.lot_code + row.date} className="border-t border-[var(--line)]">
                  <td className="px-4 py-3">{row.date}</td>
                  <td className="px-4 py-3">{row.lot_code}</td>
                  <td className="px-4 py-3">{row.vendor || "—"}</td>
                  <td className="px-4 py-3">₹{formatMoney(row.cost)}</td>
                  <td className="px-4 py-3">
                    ₹{formatMoney(row.absolute_change)} ({formatMoney(row.percent_change)}%)
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {tab === "receive" ? (
        <div className="mt-6 rounded-xl border border-[var(--line)] bg-white p-5">
          <div className="mb-4 rounded-md border border-[var(--line)] bg-[var(--paper)] p-4 font-sans text-sm">
            <p className="font-medium">Adding a new lot (same product, separate stock)</p>
            <p className="mt-1 text-[var(--muted)]">
              If this item already has stock, that older lot stays frozen with its vendor and prices. You are creating{" "}
              <strong className="text-[var(--ink)]">another lot</strong> — e.g. a different supplier or new cost/MRP/selling.
              Sales still draw older lots first (FIFO); each lot keeps its own cost.
            </p>
            <p className="mt-2 text-xs text-[var(--muted)]">
              Supplier invoice + payables? Use{" "}
              <Link to="/purchases" className="text-[var(--accent)] underline-offset-2 hover:underline">
                Supplier bills
              </Link>
              .
            </p>
          </div>
          {previous?.detected && previous.previous ? (
            <div className="mb-4 rounded-md border border-[var(--warn-line)] bg-[var(--warn-bg)] p-4 font-sans text-sm text-[var(--warn-ink)]">
              <p className="font-medium">Last lot (reference only — not overwritten)</p>
              <p className="mt-1">
                {previous.previous.lot_code}
                {previous.previous.vendor_name ? ` · ${previous.previous.vendor_name}` : " · no vendor on file"} · cost ₹
                {formatMoney(previous.previous.purchase_cost)} · sell ₹{formatMoney(previous.previous.selling_price)} ·
                safe ₹{formatMoney(previous.previous.safe_selling_price)} · still{" "}
                {formatMoney(previous.previous.remaining_quantity)} left
              </p>
              {previous.cost_difference && Number(form.list_purchase_price) > 0 ? (
                <p className="mt-1">
                  Your new cost differs by ₹{formatMoney(previous.cost_difference)} (
                  {formatMoney(previous.cost_percent_change)}%). Enter selling prices for{" "}
                  <strong>this</strong> lot.
                </p>
              ) : (
                <p className="mt-1">Enter this lot’s cost and selling prices below. Different vendor is fine.</p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="rounded-md border border-[var(--line)] px-3 py-1.5 text-[var(--ink)]" onClick={copyPrevious}>
                  Start from last lot’s prices
                </button>
                <button
                  type="button"
                  className="rounded-md border border-[var(--line)] px-3 py-1.5 text-[var(--ink)]"
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      pricing_mode: "NEW",
                      selling_price: "",
                      safe_selling_price: "",
                      mrp: "",
                      maximum_discount_percent: "0",
                    }))
                  }
                >
                  Clear — enter new prices
                </button>
              </div>
            </div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-3 font-sans text-sm">
            <label className="block md:col-span-3">
              <span className="text-xs text-[var(--muted)]">Vendor for this lot (optional)</span>
              <select
                className="mt-1 h-10 w-full rounded-md border border-[var(--line)] px-3"
                value={form.vendor_id}
                onChange={(event) => setField("vendor_id", event.target.value)}
              >
                <option value="">No vendor / cash purchase</option>
                {vendors.map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.name}
                  </option>
                ))}
              </select>
            </label>
            {[
              ["quantity", "Quantity (units in this lot)"],
              ["list_purchase_price", "Purchase price (per unit) — this lot"],
              ["supplier_discount_percent", "Supplier discount %"],
              ["mrp", "MRP (per unit) — this lot"],
              ["selling_price", "Selling price (per unit) — this lot"],
              ["safe_selling_price", "Safe selling price (per unit)"],
              ["maximum_discount_percent", "Max customer discount %"],
            ].map((pair) => (
              <label key={pair[0]} className="block">
                <span className="text-xs text-[var(--muted)]">{pair[1]}</span>
                <input
                  value={String(form[pair[0] as keyof typeof form])}
                  onChange={(event) => setField(pair[0], event.target.value)}
                  className="mt-1 h-10 w-full rounded-md border border-[var(--line)] px-3"
                />
              </label>
            ))}
            <label className="block md:col-span-3">
              <span className="text-xs text-[var(--muted)]">Lot total (this lot only)</span>
              <p className="mt-1 font-sans text-sm text-[var(--ink)]">
                {(() => {
                  const qty = Number(form.quantity) || 0;
                  const price = Number(form.list_purchase_price) || 0;
                  const discount = Number(form.supplier_discount_percent) || 0;
                  const unitCost = price * (1 - discount / 100);
                  const total = qty * unitCost;
                  return Number.isFinite(total)
                    ? `≈ ₹${formatMoney(total)} for ${formatMoney(qty)} units (₹${formatMoney(unitCost)} each after supplier discount)`
                    : "Enter quantity and purchase price to see the lot total.";
                })()}
              </p>
            </label>
          </div>
          <button type="button" className="mt-4 rounded-md bg-[var(--accent)] px-3 py-2 font-sans text-sm text-white" onClick={receiveBatch}>
            Save as new lot
          </button>
        </div>
      ) : null}
    </section>
  );
};
