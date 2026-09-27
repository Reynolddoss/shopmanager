/**
 * Catalog master data: brands, categories, subcategories, units, and tags.
 * Search keeps long lists usable; rename fixes spelling without re-linking products.
 */

import { useEffect, useState } from "react";
import { useToast } from "../hooks/useToast.ts";
import { apiClient, type Paginated } from "../services/api.ts";

type CatalogTab = "brands" | "categories" | "subcategories" | "units" | "tags";

type NamedRow = {
  id: number;
  name: string;
  is_active: boolean;
};

type UnitRow = NamedRow & { abbreviation: string };

type SubcategoryRow = NamedRow & {
  category: number;
  category_name: string;
};

const TABS: { id: CatalogTab; label: string; singular: string; hint: string }[] = [
  { id: "brands", label: "Brands", singular: "brand", hint: "Manufacturer or house brand names used on products." },
  { id: "categories", label: "Categories", singular: "category", hint: "Top-level groups (wires, switches, lighting…)." },
  {
    id: "subcategories",
    label: "Subcategories",
    singular: "subcategory",
    hint: "Optional finer groups under a category.",
  },
  { id: "units", label: "Units", singular: "unit", hint: "How stock is counted — metre, piece, box, kg…" },
  { id: "tags", label: "Tags", singular: "tag", hint: "Extra labels for search and filtering." },
];

const fieldClass = "h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm";

const endpointFor = (tab: CatalogTab) => `/${tab}/`;

export const CatalogPage = () => {
  const { push } = useToast();
  const [tab, setTab] = useState<CatalogTab>("brands");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<NamedRow[]>([]);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [subs, setSubs] = useState<SubcategoryRow[]>([]);
  const [categories, setCategories] = useState<NamedRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  // Add form drafts
  const [newName, setNewName] = useState("");
  const [newAbbr, setNewAbbr] = useState("");
  const [newCategoryId, setNewCategoryId] = useState("");
  const [busy, setBusy] = useState(false);

  // Inline edit
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editAbbr, setEditAbbr] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");

  const loadCategoriesLookup = () => {
    void apiClient
      .get<Paginated<NamedRow>>("/categories/?page_size=100")
      .then((page) => setCategories(page.results))
      .catch(() => setCategories([]));
  };

  const load = (activeTab: CatalogTab, search: string) => {
    setLoading(true);
    setMessage("");
    const q = search.trim() ? `&search=${encodeURIComponent(search.trim())}` : "";
    void apiClient
      .get<Paginated<NamedRow | UnitRow | SubcategoryRow>>(
        `${endpointFor(activeTab)}?page_size=100${q}`,
      )
      .then((page) => {
        if (activeTab === "units") setUnits(page.results as UnitRow[]);
        else if (activeTab === "subcategories") setSubs(page.results as SubcategoryRow[]);
        else setRows(page.results as NamedRow[]);
      })
      .catch((err: unknown) =>
        setMessage(err instanceof Error ? err.message : "Could not load catalog."),
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCategoriesLookup();
  }, []);

  useEffect(() => {
    setEditingId(null);
    setNewName("");
    setNewAbbr("");
    setNewCategoryId("");
  }, [tab]);

  // Reload when tab or search changes (search is lightly debounced).
  useEffect(() => {
    const handle = window.setTimeout(() => load(tab, query), query ? 250 : 0);
    return () => window.clearTimeout(handle);
  }, [tab, query]);

  const resetEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditAbbr("");
    setEditCategoryId("");
  };

  const startEdit = (row: NamedRow | UnitRow | SubcategoryRow) => {
    setEditingId(row.id);
    setEditName(row.name);
    setEditAbbr("abbreviation" in row ? row.abbreviation : "");
    setEditCategoryId("category" in row ? String(row.category) : "");
  };

  const create = () => {
    const name = newName.trim();
    if (!name) {
      push("error", "Name needed", "Enter a name before adding.");
      return;
    }
    setBusy(true);
    let body: Record<string, unknown> = { name, is_active: true };
    if (tab === "units") {
      body = {
        ...body,
        abbreviation: newAbbr.trim() || name.slice(0, 3).toLowerCase(),
      };
    }
    if (tab === "subcategories") {
      if (!newCategoryId) {
        push("error", "Category needed", "Pick a parent category for this subcategory.");
        setBusy(false);
        return;
      }
      body = { ...body, category: Number(newCategoryId) };
    }
    void apiClient
      .post(endpointFor(tab), body)
      .then(() => {
        push("success", "Added", `"${name}" is ready.`);
        setNewName("");
        setNewAbbr("");
        setNewCategoryId("");
        load(tab, query);
        if (tab === "categories") loadCategoriesLookup();
      })
      .catch((err: unknown) =>
        push("error", "Not saved", err instanceof Error ? err.message : "Request failed."),
      )
      .finally(() => setBusy(false));
  };

  const saveEdit = () => {
    if (editingId == null) return;
    const name = editName.trim();
    if (!name) {
      push("error", "Name needed", "Enter the corrected spelling.");
      return;
    }
    setBusy(true);
    let body: Record<string, unknown> = { name };
    if (tab === "units") {
      body = { ...body, abbreviation: editAbbr.trim() || name.slice(0, 3).toLowerCase() };
    }
    if (tab === "subcategories") {
      if (!editCategoryId) {
        push("error", "Category needed", "Pick a parent category.");
        setBusy(false);
        return;
      }
      body = { ...body, category: Number(editCategoryId) };
    }
    void apiClient
      .patch(`${endpointFor(tab)}${editingId}/`, body)
      .then(() => {
        push("success", "Updated", `Saved as "${name}".`);
        resetEdit();
        load(tab, query);
        if (tab === "categories") loadCategoriesLookup();
      })
      .catch((err: unknown) =>
        push("error", "Not saved", err instanceof Error ? err.message : "Request failed."),
      )
      .finally(() => setBusy(false));
  };

  const toggleActive = (row: NamedRow) => {
    void apiClient
      .patch(`${endpointFor(tab)}${row.id}/`, { is_active: !row.is_active })
      .then(() => load(tab, query))
      .catch((err: unknown) =>
        push("error", "Not updated", err instanceof Error ? err.message : "Request failed."),
      );
  };

  const list =
    tab === "units" ? units : tab === "subcategories" ? subs : rows;

  const activeTabMeta = TABS.find((item) => item.id === tab)!;

  return (
    <section>
      <h2 className="text-3xl">Catalog</h2>
      <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
        Add or rename brands, categories, units, and tags. Fixing a spelling updates every product that uses that
        name — you do not need to re-link each item.
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={[
              "h-9 rounded-md px-3 font-sans text-sm",
              tab === item.id
                ? "bg-[var(--accent)] text-[var(--on-accent)]"
                : "border border-[var(--line)] bg-[var(--panel)] text-[var(--ink)]",
            ].join(" ")}
          >
            {item.label}
          </button>
        ))}
      </div>

      <p className="mt-3 font-sans text-sm text-[var(--muted)]">{activeTabMeta.hint}</p>
      {message ? <p className="mt-2 font-sans text-sm text-[var(--danger)]">{message}</p> : null}

      <div className="mt-6 max-w-xl rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[var(--shadow)]">
        <p className="font-sans text-xs tracking-[0.12em] text-[var(--muted)] uppercase">Add {activeTabMeta.singular}</p>
        <div className="mt-3 grid gap-2">
          {tab === "subcategories" ? (
            <label className="block font-sans text-sm">
              <span className="text-xs text-[var(--muted)]">Parent category</span>
              <select
                className={`${fieldClass} mt-1`}
                value={newCategoryId}
                onChange={(e) => setNewCategoryId(e.target.value)}
              >
                <option value="">Select category</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="block font-sans text-sm">
            <span className="text-xs text-[var(--muted)]">Name</span>
            <input
              className={`${fieldClass} mt-1`}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  create();
                }
              }}
              placeholder={`New ${activeTabMeta.singular} name`}
            />
          </label>
          {tab === "units" ? (
            <label className="block font-sans text-sm">
              <span className="text-xs text-[var(--muted)]">Abbreviation</span>
              <input
                className={`${fieldClass} mt-1`}
                value={newAbbr}
                onChange={(e) => setNewAbbr(e.target.value)}
                placeholder="m, pc, box…"
              />
            </label>
          ) : null}
          <button
            type="button"
            disabled={busy}
            className="h-10 rounded-md bg-[var(--accent)] px-3 font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
            onClick={create}
          >
            {busy ? "Saving…" : `Add ${activeTabMeta.singular}`}
          </button>
        </div>
      </div>

      <div className="mt-8 max-w-2xl">
        <label className="block font-sans text-sm">
          <span className="text-xs text-[var(--muted)]">Search</span>
          <input
            className={`${fieldClass} mt-1`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Find ${activeTabMeta.label.toLowerCase()}…`}
          />
        </label>

        {loading ? (
          <p className="mt-4 font-sans text-sm text-[var(--muted)]">Loading…</p>
        ) : list.length === 0 ? (
          <p className="mt-4 font-sans text-sm text-[var(--muted)]">
            {query.trim() ? "No matches." : `No ${activeTabMeta.label.toLowerCase()} yet.`}
          </p>
        ) : (
          <ul className="mt-4 space-y-2 font-sans text-sm">
            {list.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] py-2"
              >
                {editingId === row.id ? (
                  <div className="flex min-w-0 flex-1 flex-col gap-2">
                    {tab === "subcategories" ? (
                      <select
                        className={fieldClass}
                        value={editCategoryId}
                        onChange={(e) => setEditCategoryId(e.target.value)}
                      >
                        {categories.map((cat) => (
                          <option key={cat.id} value={cat.id}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      <input
                        autoFocus
                        className="h-9 min-w-0 flex-1 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            saveEdit();
                          }
                        }}
                      />
                      {tab === "units" ? (
                        <input
                          className="h-9 w-24 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3"
                          value={editAbbr}
                          onChange={(e) => setEditAbbr(e.target.value)}
                          placeholder="abbr"
                        />
                      ) : null}
                      <button
                        type="button"
                        disabled={busy}
                        className="h-9 rounded-md bg-[var(--accent)] px-3 text-[var(--on-accent)] disabled:opacity-60"
                        onClick={saveEdit}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="h-9 rounded-md border border-[var(--line)] px-3"
                        onClick={resetEdit}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="min-w-0">
                      <span className={row.is_active ? "" : "text-[var(--muted)] line-through"}>
                        {tab === "subcategories" && "category_name" in row
                          ? `${row.category_name} / ${row.name}`
                          : tab === "units" && "abbreviation" in row
                            ? `${row.name} (${row.abbreviation})`
                            : row.name}
                      </span>
                      {!row.is_active ? (
                        <span className="ml-2 text-[11px] text-[var(--muted)]">inactive</span>
                      ) : null}
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="rounded border border-[var(--line)] px-2 py-1"
                        onClick={() => startEdit(row)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded border border-[var(--line)] px-2 py-1 text-[var(--muted)]"
                        onClick={() => toggleActive(row)}
                      >
                        {row.is_active ? "Hide" : "Show"}
                      </button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
};
