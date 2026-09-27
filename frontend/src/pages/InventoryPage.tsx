import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../components/States.tsx";
import { apiClient, type FinderRow, type NamedRef, type Paginated } from "../services/api.ts";
import { formatMoney } from "../utils/money.ts";

const statusLabel = (status: string) => {
  if (status === "out_of_stock") {
    return "Out of stock";
  }
  if (status === "low_stock") {
    return "Low stock";
  }
  return "In stock";
};

export const InventoryPage = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [stockStatus, setStockStatus] = useState("");
  const [rows, setRows] = useState<FinderRow[]>([]);
  const [categories, setCategories] = useState<NamedRef[]>([]);
  const [brands, setBrands] = useState<NamedRef[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void Promise.all([
      apiClient.get<Paginated<NamedRef>>("/categories/"),
      apiClient.get<Paginated<NamedRef>>("/brands/"),
    ]).then(([categoryPage, brandPage]) => {
      setCategories(categoryPage.results);
      setBrands(brandPage.results);
    });
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query) {
      params.set("q", query);
    }
    if (category) {
      params.set("category", category);
    }
    if (brand) {
      params.set("brand", brand);
    }
    if (stockStatus) {
      params.set("stock_status", stockStatus);
    }
    setState("loading");
    const handle = window.setTimeout(() => {
      void apiClient
        .get<Paginated<FinderRow>>(`/products/finder/?${params.toString()}`)
        .then((payload) => {
          setRows(payload.results);
          setState("ready");
        })
        .catch((error: unknown) => {
          setState("error");
          setMessage(error instanceof Error ? error.message : "Could not load inventory.");
        });
    }, 120);
    return () => window.clearTimeout(handle);
  }, [query, category, brand, stockStatus]);

  return (
    <section>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl">Inventory</h2>
          <p className="mt-2 max-w-2xl font-sans text-sm leading-6 text-[var(--muted)]">
            Search the catalog without loading it into the browser. Stock, cost, and selling prices come from live batches.
          </p>
        </div>
        <Link
          to="/inventory/new"
          className="rounded-md bg-[var(--accent)] px-3 py-2 font-sans text-sm text-white"
        >
          New product
        </Link>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-4">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Name, SKU, alias, HSN, vendor SKU…"
          className="h-10 rounded-md border border-[var(--line)] bg-white px-3 font-sans text-sm"
        />
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="h-10 rounded-md border border-[var(--line)] bg-white px-3 font-sans text-sm"
        >
          <option value="">All categories</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <select
          value={brand}
          onChange={(event) => setBrand(event.target.value)}
          className="h-10 rounded-md border border-[var(--line)] bg-white px-3 font-sans text-sm"
        >
          <option value="">All brands</option>
          {brands.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <select
          value={stockStatus}
          onChange={(event) => setStockStatus(event.target.value)}
          className="h-10 rounded-md border border-[var(--line)] bg-white px-3 font-sans text-sm"
        >
          <option value="">All stock</option>
          <option value="in_stock">In stock</option>
          <option value="low_stock">Low stock</option>
          <option value="out_of_stock">Out of stock</option>
        </select>
      </div>
      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--line)] bg-white">
        {state === "loading" ? <LoadingState label="Searching catalog…" /> : null}
        {state === "error" ? <ErrorState message={message} /> : null}
        {state === "ready" && rows.length === 0 ? (
          <EmptyState title="No products match" body="Try a shorter token such as 2.5, mcb, or a brand name." />
        ) : null}
        {state === "ready" && rows.length > 0 ? (
          <table className="w-full font-sans text-sm">
            <thead className="bg-[var(--paper)] text-left text-xs tracking-wide text-[var(--muted)] uppercase">
              <tr>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Stock</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Selling</th>
                <th className="px-4 py-3">Safe</th>
                <th className="px-4 py-3">Vendor</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer border-t border-[var(--line)] hover:bg-[var(--paper)]"
                  onClick={() => navigate(`/inventory/${row.id}`)}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-11 w-11 shrink-0 overflow-hidden rounded-md border border-[var(--line)] bg-[var(--paper)]">
                        {row.image_url ? (
                          <img src={row.image_url} alt="" className="h-full w-full object-cover" />
                        ) : null}
                      </div>
                      <div>
                        <p className="font-medium">{row.name}</p>
                        <p className="text-xs text-[var(--muted)]">
                          {row.sku} · {row.brand_name} · {row.specification || "—"}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {formatMoney(row.current_stock)}
                    <span className="ml-2 text-xs text-[var(--muted)]">{statusLabel(row.stock_status)}</span>
                  </td>
                  <td className="px-4 py-3">{row.active_cost ? `₹${formatMoney(row.active_cost)}` : "—"}</td>
                  <td className="px-4 py-3">{row.active_selling_price ? `₹${formatMoney(row.active_selling_price)}` : "—"}</td>
                  <td className="px-4 py-3">{row.active_safe_selling_price ? `₹${formatMoney(row.active_safe_selling_price)}` : "—"}</td>
                  <td className="px-4 py-3">
                    {row.preferred_vendor || (row.last_purchase_price ? `₹${formatMoney(row.last_purchase_price)}` : "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
    </section>
  );
};
