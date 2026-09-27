import { useEffect, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, type FinderRow, type Paginated } from "../services/api.ts";

type SmartFinderProps = {
  query: string;
  onQueryChange: (value: string) => void;
};

/**
 * Global product finder. Results come from Django; the browser never loads the catalog.
 */
export const SmartFinder = ({ query, onQueryChange }: SmartFinderProps) => {
  const navigate = useNavigate();
  const [rows, setRows] = useState<FinderRow[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (query.trim().length < 1) {
      setRows([]);
      setOpen(false);
      return;
    }
    const handle = window.setTimeout(() => {
      void apiClient
        .get<Paginated<FinderRow>>(`/products/finder/?q=${encodeURIComponent(query)}`)
        .then((payload) => {
          setRows(payload.results);
          setActive(0);
          setOpen(true);
        })
        .catch(() => {
          setRows([]);
        });
    }, 160);
    return () => window.clearTimeout(handle);
  }, [query]);

  const openProduct = (row: FinderRow) => {
    setOpen(false);
    navigate(`/inventory/${row.id}`);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, Math.max(rows.length - 1, 0)));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    }
    if (event.key === "Enter" && rows[active]) {
      event.preventDefault();
      openProduct(rows[active]);
    }
    if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative flex-1">
      <input
        type="search"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Find product — name, SKU, 2.5 wire, polycab, mcb 16…"
        className="h-9 w-full rounded-md border border-[var(--line)] bg-[var(--paper)] px-3 font-sans text-sm outline-none"
      />
      {open && rows.length > 0 ? (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--panel)] shadow-[var(--shadow)]">
          {rows.map((row, index) => (
            <button
              key={row.id}
              type="button"
              className={[
                "flex w-full items-start justify-between gap-4 px-4 py-3 text-left font-sans text-sm",
                index === active ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--paper)]",
              ].join(" ")}
              onMouseEnter={() => setActive(index)}
              onClick={() => openProduct(row)}
            >
              <span>
                <span className="block font-medium text-[var(--ink)]">{row.name}</span>
                <span className="mt-0.5 block text-xs text-[var(--muted)]">
                  {row.sku} · {row.brand_name || "No brand"} · {row.category_name}
                </span>
              </span>
              <span className="shrink-0 text-right text-xs">
                <span className="block">{row.current_stock} in stock</span>
                <span className="block text-[var(--muted)]">
                  {row.active_selling_price ? `₹${row.active_selling_price}` : "No batch"}
                </span>
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
};
