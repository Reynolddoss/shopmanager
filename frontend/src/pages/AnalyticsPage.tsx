import { useEffect, useState } from "react";
import { apiClient } from "../services/api.ts";

type NamedMoney = { name?: string; sku?: string; total?: string; revenue?: string; qty?: string; gross_profit?: string };
type SalesPayload = {
  invoice_count: number;
  gross_sales: string;
  average_bill_value: string;
  sales_growth_percent: string;
  series: { daily: { period: string; total: string }[] };
  top_products: NamedMoney[];
  top_brands: NamedMoney[];
  top_customers: { name: string; revenue: string }[];
};
type ProfitPayload = {
  gross_sales: string;
  cost_of_goods: string;
  gross_profit: string;
  gross_margin_percent: string;
  by_product: NamedMoney[];
  by_brand: NamedMoney[];
};
type InventoryPayload = {
  stock_value: string;
  on_hand_quantity: string;
  low_stock_count: number;
  out_of_stock_count: number;
  dead_stock: { sku: string; name: string }[];
  fast_moving: { sku: string; name: string }[];
};
type PurchasePayload = { total_purchases: string; bill_count: number; by_vendor: { name: string; total: string }[] };
type VendorPayload = { vendors: { name: string; total_purchases: string; best_historical_price: string; outstanding: string }[] };
type DiscountPayload = { discount_total: string; average_discount: string; safe_price_overrides: number; margin_eroders: { sku: string; name: string }[] };
type CustomerPayload = {
  customers: {
    name: string;
    phone?: string;
    customer_type?: string;
    purchase_value: string;
    outstanding: string;
    invoices?: number;
  }[];
};
type ExpensePayload = { total_expenses: string; by_category: { name: string; total: string }[] };
type BatchPayload = {
  batches: {
    sku: string;
    lot_code: string;
    cost: string;
    selling_price: string;
    remaining_quantity: string;
    age_days: number;
  }[];
};
type Lookup = { id: number; name: string };

const tabs = ["Sales", "Profit", "Inventory", "Purchases", "Vendors", "Batches", "Discounts", "Customers", "Expenses"] as const;
type Tab = (typeof tabs)[number];

const qs = (from: string, to: string, categoryId: string, brandId: string) => {
  const extra = [categoryId ? `category_id=${categoryId}` : "", brandId ? `brand_id=${brandId}` : ""].filter(Boolean).join("&");
  return extra ? `date_from=${from}&date_to=${to}&${extra}` : `date_from=${from}&date_to=${to}`;
};

const Bar = ({ label, value, max }: { label: string; value: string; max: number }) => {
  const n = Number(value) || 0;
  const width = max > 0 ? Math.max(4, Math.round((n / max) * 100)) : 4;
  return (
    <div className="mb-2">
      <div className="flex justify-between font-sans text-xs">
        <span>{label}</span>
        <span>₹{value}</span>
      </div>
      <div className="mt-1 h-2 rounded bg-[var(--accent-soft)]">
        <div className="h-2 rounded bg-[var(--accent)]" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
};

export const AnalyticsPage = () => {
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = `${today.slice(0, 8)}01`;
  const [tab, setTab] = useState<Tab>("Sales");
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(today);
  const [categoryId, setCategoryId] = useState("");
  const [brandId, setBrandId] = useState("");
  const [categories, setCategories] = useState<Lookup[]>([]);
  const [brands, setBrands] = useState<Lookup[]>([]);
  const [sales, setSales] = useState<SalesPayload | null>(null);
  const [profit, setProfit] = useState<ProfitPayload | null>(null);
  const [inventory, setInventory] = useState<InventoryPayload | null>(null);
  const [purchases, setPurchases] = useState<PurchasePayload | null>(null);
  const [vendors, setVendors] = useState<VendorPayload | null>(null);
  const [discounts, setDiscounts] = useState<DiscountPayload | null>(null);
  const [customers, setCustomers] = useState<CustomerPayload | null>(null);
  const [expenses, setExpenses] = useState<ExpensePayload | null>(null);
  const [batches, setBatches] = useState<BatchPayload | null>(null);

  useEffect(() => {
    void apiClient.get<{ results: Lookup[] }>("/categories/").then((page) => setCategories(page.results));
    void apiClient.get<{ results: Lookup[] }>("/brands/").then((page) => setBrands(page.results));
  }, []);

  useEffect(() => {
    const q = qs(from, to, categoryId, brandId);
    void apiClient.get<SalesPayload>(`/analytics/sales/?${q}`).then(setSales);
    void apiClient.get<ProfitPayload>(`/analytics/profit/?${q}`).then(setProfit);
    void apiClient.get<InventoryPayload>("/analytics/inventory/").then(setInventory);
    void apiClient.get<PurchasePayload>(`/analytics/purchases/?${q}`).then(setPurchases);
    void apiClient.get<VendorPayload>(`/analytics/vendors/?${q}`).then(setVendors);
    void apiClient.get<DiscountPayload>(`/analytics/discounts/?${q}`).then(setDiscounts);
    void apiClient.get<CustomerPayload>(`/analytics/customers/?${q}`).then(setCustomers);
    void apiClient.get<ExpensePayload>(`/analytics/expenses/?${q}`).then(setExpenses);
    void apiClient.get<BatchPayload>("/analytics/batches/").then(setBatches);
  }, [from, to, categoryId, brandId]);

  const exportUrl = (report: string) => `/api/v1/analytics/export/${report}/?${qs(from, to, categoryId, brandId)}`;

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl">Analytics</h2>
          <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
            Aggregates run on Django. Profit uses historical lot cost, not the product’s current purchase price.
          </p>
        </div>
        <div className="flex gap-2 font-sans text-sm">
          <input type="date" className="h-10 rounded-md border px-2" value={from} onChange={(e) => setFrom(e.target.value)} />
          <input type="date" className="h-10 rounded-md border px-2" value={to} onChange={(e) => setTo(e.target.value)} />
          <select className="h-10 rounded-md border px-2" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
          <select className="h-10 rounded-md border px-2" value={brandId} onChange={(e) => setBrandId(e.target.value)}>
            <option value="">All brands</option>
            {brands.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
          <a className="h-10 rounded-md border px-3 leading-10" href={exportUrl(tab.toLowerCase())}>CSV</a>
          <button type="button" className="h-10 rounded-md border px-3" onClick={() => window.print()}>Print</button>
        </div>
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        {tabs.map((item) => (
          <button
            key={item}
            type="button"
            className={`rounded-full px-3 py-1 font-sans text-sm ${tab === item ? "bg-[var(--accent)] text-white" : "border"}`}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="mt-6 rounded-xl border border-[var(--line)] bg-white p-6">
        {tab === "Sales" && sales ? (
          <div>
            <p className="font-sans text-sm">Invoices {sales.invoice_count} · Sales ₹{sales.gross_sales} · Avg bill ₹{sales.average_bill_value} · Growth {sales.sales_growth_percent}%</p>
            <div className="mt-4 max-w-xl">
              {sales.series.daily.map((row) => (
                <Bar key={row.period} label={row.period} value={row.total} max={Math.max(...sales.series.daily.map((item) => Number(item.total) || 0), 1)} />
              ))}
            </div>
            <p className="mt-4 font-sans text-xs text-[var(--muted)]">Top products: {sales.top_products.map((row) => row.sku).join(", ") || "—"}</p>
            <p className="mt-1 font-sans text-xs text-[var(--muted)]">Top brands: {sales.top_brands.map((row) => row.name).join(", ") || "—"}</p>
            <p className="mt-1 font-sans text-xs text-[var(--muted)]">Top customers: {sales.top_customers.map((row) => row.name).join(", ") || "—"}</p>
          </div>
        ) : null}
        {tab === "Profit" && profit ? (
          <div>
            <p className="font-sans text-sm">Gross ₹{profit.gross_sales} · COGS ₹{profit.cost_of_goods} · Profit ₹{profit.gross_profit} ({profit.gross_margin_percent}%)</p>
            <ul className="mt-4 font-sans text-sm">
              {profit.by_product.map((row) => (
                <li key={row.sku}>{row.sku} {row.name} · profit ₹{row.gross_profit}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {tab === "Inventory" && inventory ? (
          <div className="font-sans text-sm">
            <p>Value ₹{inventory.stock_value} · On hand {inventory.on_hand_quantity} · Low {inventory.low_stock_count} · Out {inventory.out_of_stock_count}</p>
            <p className="mt-3">Fast moving: {inventory.fast_moving.map((item) => item.sku).join(", ") || "—"}</p>
            <p className="mt-1">Dead stock: {inventory.dead_stock.map((item) => item.sku).join(", ") || "—"}</p>
          </div>
        ) : null}
        {tab === "Purchases" && purchases ? (
          <p className="font-sans text-sm">Bills {purchases.bill_count} · Total ₹{purchases.total_purchases}</p>
        ) : null}
        {tab === "Batches" && batches ? (
          <ul className="font-sans text-sm">
            {batches.batches.slice(0, 40).map((lot) => (
              <li key={lot.lot_code}>
                {lot.sku} {lot.lot_code} · cost ₹{lot.cost} · sell ₹{lot.selling_price} · qty {lot.remaining_quantity} · {lot.age_days}d
              </li>
            ))}
          </ul>
        ) : null}
        {tab === "Vendors" && vendors ? (
          <ul className="font-sans text-sm">
            {vendors.vendors.map((vendor) => (
              <li key={vendor.name}>{vendor.name} · ₹{vendor.total_purchases} · best ₹{vendor.best_historical_price} · due ₹{vendor.outstanding}</li>
            ))}
          </ul>
        ) : null}
        {tab === "Discounts" && discounts ? (
          <p className="font-sans text-sm">Discounts ₹{discounts.discount_total} · avg ₹{discounts.average_discount} · safe overrides {discounts.safe_price_overrides}</p>
        ) : null}
        {tab === "Customers" && customers ? (
          <ul className="space-y-2 font-sans text-sm">
            {customers.customers.map((customer) => (
              <li key={`${customer.name}-${customer.phone || ""}`} className="border-t border-[var(--line)] pt-2 first:border-t-0 first:pt-0">
                <span className="font-medium">{customer.name}</span>
                <span className="text-[var(--muted)]">
                  {customer.customer_type ? ` · ${customer.customer_type}` : ""}
                  {customer.phone ? ` · ${customer.phone}` : ""}
                  {customer.invoices != null ? ` · ${customer.invoices} visits` : ""}
                </span>
                <div className="text-xs text-[var(--muted)]">
                  Purchases ₹{customer.purchase_value} · due ₹{customer.outstanding}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
        {tab === "Expenses" && expenses ? (
          <p className="font-sans text-sm">Total ₹{expenses.total_expenses}</p>
        ) : null}
      </div>
    </section>
  );
};
