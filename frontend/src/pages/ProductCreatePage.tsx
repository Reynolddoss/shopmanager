import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ProductImageField } from "../components/ProductImageField.tsx";
import { useToast } from "../hooks/useToast.ts";
import { apiClient, type NamedRef, type Paginated } from "../services/api.ts";

const fieldClass = "mt-1 h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3";

/** Small circled “i” that shows a short explanation on hover. */
const FieldHint = ({ text }: { text: string }) => (
  <span className="group relative ml-1.5 inline-flex align-middle">
    <span
      className="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-[var(--muted)] text-[9px] leading-none text-[var(--muted)]"
      aria-label={text}
      tabIndex={0}
    >
      i
    </span>
    <span
      role="tooltip"
      className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-52 -translate-x-1/2 rounded-md border border-[var(--line)] bg-[var(--panel)] px-2.5 py-2 text-left text-[11px] leading-snug font-normal text-[var(--ink)] opacity-0 shadow-[var(--shadow)] transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
    >
      {text}
    </span>
  </span>
);

const FieldLabel = ({ children, hint }: { children: React.ReactNode; hint: string }) => (
  <span className="inline-flex items-center text-xs text-[var(--muted)]">
    {children}
    <FieldHint text={hint} />
  </span>
);

type ProductForm = {
  name: string;
  sku: string;
  barcode: string;
  category: string;
  brand: string;
  unit: string;
  vendor: string;
  vendor_sku: string;
  specificationTags: string[];
  hsn_code: string;
  alias_terms: string;
  min_stock_quantity: string;
  reorder_level: string;
};

type WizardStep = {
  id: string;
  title: string;
  blurb: string;
};

const STEPS: WizardStep[] = [
  { id: "identity", title: "Identity", blurb: "What is this item called, and how will you find it?" },
  { id: "classify", title: "Classify", blurb: "Category, brand, unit, and optional preferred vendor." },
  { id: "details", title: "Details", blurb: "Optional specs, HSN, and search aliases." },
  { id: "stock", title: "Stock alerts", blurb: "Low-stock thresholds only — quantity on hand is received after create." },
];

type UnitRef = NamedRef & { abbreviation?: string };

type CreatableNamedSelectProps = {
  label: string;
  hint: string;
  value: string;
  options: NamedRef[];
  optional?: boolean;
  createPath: string;
  optionLabel?: (item: NamedRef) => string;
  onChange: (value: string) => void;
  onCreated: (row: NamedRef) => void;
  /** Keep local lists in sync after a rename (same id, new name). */
  onUpdated?: (row: NamedRef) => void;
};

const CreatableNamedSelect = ({
  label,
  hint,
  value,
  options,
  optional = false,
  createPath,
  optionLabel = (item) => item.name,
  onChange,
  onCreated,
  onUpdated,
}: CreatableNamedSelectProps) => {
  const { push } = useToast();
  /** idle | adding a new name | renaming the selected row */
  const [mode, setMode] = useState<"idle" | "add" | "rename">("idle");
  const [draftName, setDraftName] = useState("");
  const [busy, setBusy] = useState(false);

  const selected = options.find((item) => String(item.id) === value);

  const create = () => {
    const name = draftName.trim();
    if (!name) {
      push("error", `Missing ${label.toLowerCase()}`, "Enter a name before adding.");
      return;
    }
    setBusy(true);
    void apiClient
      .post<NamedRef>(createPath, { name, is_active: true })
      .then((row) => {
        onCreated(row);
        onChange(String(row.id));
        setDraftName("");
        setMode("idle");
        push("success", `${label} added`, `"${row.name}" is ready to use.`);
      })
      .catch((err: unknown) =>
        push("error", `Could not add ${label.toLowerCase()}`, err instanceof Error ? err.message : "Request failed."),
      )
      .finally(() => setBusy(false));
  };

  const rename = () => {
    if (!selected) return;
    const name = draftName.trim();
    if (!name) {
      push("error", `Missing ${label.toLowerCase()}`, "Enter the corrected spelling.");
      return;
    }
    if (name === selected.name) {
      setMode("idle");
      return;
    }
    setBusy(true);
    void apiClient
      .patch<NamedRef>(`${createPath}${selected.id}/`, { name })
      .then((row) => {
        onUpdated?.(row);
        setDraftName("");
        setMode("idle");
        push("success", `${label} updated`, `Renamed to "${row.name}".`);
      })
      .catch((err: unknown) =>
        push(
          "error",
          `Could not rename ${label.toLowerCase()}`,
          err instanceof Error ? err.message : "Request failed.",
        ),
      )
      .finally(() => setBusy(false));
  };

  return (
    <div className="block">
      <FieldLabel hint={hint}>{label}</FieldLabel>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={fieldClass}
        disabled={mode !== "idle"}
      >
        <option value="">{optional ? "None" : "Select"}</option>
        {options.map((item) => (
          <option key={item.id} value={item.id}>
            {optionLabel(item)}
          </option>
        ))}
      </select>
      {mode === "idle" ? (
        <div className="mt-2 flex flex-wrap gap-3">
          <button
            type="button"
            className="font-sans text-xs text-[var(--accent)] underline-offset-2 hover:underline"
            onClick={() => {
              setMode("add");
              setDraftName("");
            }}
          >
            + Add new {label.toLowerCase()}
          </button>
          {selected ? (
            <button
              type="button"
              className="font-sans text-xs text-[var(--muted)] underline-offset-2 hover:underline"
              onClick={() => {
                setMode("rename");
                setDraftName(selected.name);
              }}
            >
              Rename “{selected.name}”
            </button>
          ) : null}
        </div>
      ) : (
        <div className="mt-2 flex gap-2">
          <input
            autoFocus
            className="h-9 min-w-0 flex-1 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
            placeholder={mode === "rename" ? `Correct ${label.toLowerCase()} spelling` : `New ${label.toLowerCase()} name`}
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                if (mode === "rename") rename();
                else create();
              }
            }}
          />
          <button
            type="button"
            disabled={busy}
            className="h-9 rounded-md bg-[var(--accent)] px-3 font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
            onClick={() => (mode === "rename" ? rename() : create())}
          >
            {busy ? "…" : mode === "rename" ? "Save" : "Add"}
          </button>
          <button
            type="button"
            className="h-9 rounded-md border border-[var(--line)] px-3 font-sans text-sm"
            onClick={() => {
              setMode("idle");
              setDraftName("");
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};

type CreatableUnitSelectProps = {
  label: string;
  hint: string;
  value: string;
  options: UnitRef[];
  onChange: (value: string) => void;
  onCreated: (row: UnitRef) => void;
};

/** Unit needs both a full name and a short abbreviation (e.g. Metre / m). */
const CreatableUnitSelect = ({ label, hint, value, options, onChange, onCreated }: CreatableUnitSelectProps) => {
  const { push } = useToast();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [abbreviation, setAbbreviation] = useState("");
  const [busy, setBusy] = useState(false);

  const create = () => {
    const unitName = name.trim();
    const abbr = abbreviation.trim() || unitName.slice(0, 3).toLowerCase();
    if (!unitName) {
      push("error", "Missing unit", "Enter a unit name before adding.");
      return;
    }
    setBusy(true);
    void apiClient
      .post<UnitRef>("/units/", { name: unitName, abbreviation: abbr, is_active: true })
      .then((row) => {
        onCreated(row);
        onChange(String(row.id));
        setName("");
        setAbbreviation("");
        setAdding(false);
        push("success", "Unit added", `${row.name} (${row.abbreviation || abbr}) is ready.`);
      })
      .catch((err: unknown) =>
        push("error", "Could not add unit", err instanceof Error ? err.message : "Request failed."),
      )
      .finally(() => setBusy(false));
  };

  return (
    <div className="block">
      <FieldLabel hint={hint}>{label}</FieldLabel>
      <select value={value} onChange={(event) => onChange(event.target.value)} className={fieldClass} disabled={adding}>
        <option value="">Select</option>
        {options.map((item) => (
          <option key={item.id} value={item.id}>
            {item.abbreviation ? `${item.name} (${item.abbreviation})` : item.name}
          </option>
        ))}
      </select>
      {!adding ? (
        <button
          type="button"
          className="mt-2 font-sans text-xs text-[var(--accent)] underline-offset-2 hover:underline"
          onClick={() => setAdding(true)}
        >
          + Add new unit
        </button>
      ) : (
        <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_7rem_auto_auto]">
          <input
            autoFocus
            className="h-9 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
            placeholder="Unit name — e.g. Metre"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <input
            className="h-9 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
            placeholder="Abbr — m"
            value={abbreviation}
            onChange={(event) => setAbbreviation(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                create();
              }
            }}
          />
          <button
            type="button"
            disabled={busy}
            className="h-9 rounded-md bg-[var(--accent)] px-3 font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
            onClick={create}
          >
            {busy ? "…" : "Add"}
          </button>
          <button
            type="button"
            className="h-9 rounded-md border border-[var(--line)] px-3 font-sans text-sm"
            onClick={() => {
              setAdding(false);
              setName("");
              setAbbreviation("");
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};

type CreatableVendorSelectProps = {
  label: string;
  hint: string;
  value: string;
  options: NamedRef[];
  onChange: (value: string) => void;
  onCreated: (row: NamedRef) => void;
};

/** Link an existing supplier or create one inline while adding a product. */
const CreatableVendorSelect = ({ label, hint, value, options, onChange, onCreated }: CreatableVendorSelectProps) => {
  const { push } = useToast();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);

  const create = () => {
    const vendorName = name.trim();
    if (!vendorName) {
      push("error", "Missing vendor", "Enter a supplier name before adding.");
      return;
    }
    setBusy(true);
    void apiClient
      .post<NamedRef>("/vendors/", { name: vendorName, phone: phone.trim(), is_active: true })
      .then((row) => {
        onCreated(row);
        onChange(String(row.id));
        setName("");
        setPhone("");
        setAdding(false);
        push("success", "Vendor added", `"${row.name}" is linked as preferred supplier.`);
      })
      .catch((err: unknown) =>
        push("error", "Could not add vendor", err instanceof Error ? err.message : "Request failed."),
      )
      .finally(() => setBusy(false));
  };

  return (
    <div className="block">
      <FieldLabel hint={hint}>{label}</FieldLabel>
      <select value={value} onChange={(event) => onChange(event.target.value)} className={fieldClass} disabled={adding}>
        <option value="">None — link later</option>
        {options.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
      {!adding ? (
        <button
          type="button"
          className="mt-2 font-sans text-xs text-[var(--accent)] underline-offset-2 hover:underline"
          onClick={() => setAdding(true)}
        >
          + Add new vendor
        </button>
      ) : (
        <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_8rem_auto_auto]">
          <input
            autoFocus
            className="h-9 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
            placeholder="Supplier name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <input
            className="h-9 rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
            placeholder="Phone (optional)"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                create();
              }
            }}
          />
          <button
            type="button"
            disabled={busy}
            className="h-9 rounded-md bg-[var(--accent)] px-3 font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
            onClick={create}
          >
            {busy ? "…" : "Add"}
          </button>
          <button
            type="button"
            className="h-9 rounded-md border border-[var(--line)] px-3 font-sans text-sm"
            onClick={() => {
              setAdding(false);
              setName("");
              setPhone("");
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};

/**
 * Specification as removable chips. Stored on the product as a joined string
 * so existing list/detail screens keep working without a schema change.
 */
const SpecTagsField = ({
  tags,
  onChange,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
}) => {
  const [draft, setDraft] = useState("");

  const addTag = (raw: string) => {
    const next = raw
      .split(",")
      .map((part) => part.trim())
      .filter((part) => part.length > 0);
    if (!next.length) {
      return;
    }
    const merged = [...tags];
    next.forEach((tag) => {
      if (!merged.some((existing) => existing.toLowerCase() === tag.toLowerCase())) {
        merged.push(tag);
      }
    });
    onChange(merged);
    setDraft("");
  };

  const removeTag = (index: number) => onChange(tags.filter((_, i) => i !== index));

  return (
    <div className="block">
      <FieldLabel hint="Short attribute chips — size, colour, material, rating. Add one at a time or paste comma-separated values. Click × to remove.">
        Specification (optional)
      </FieldLabel>
      <div className="mt-1 rounded-md border border-[var(--line)] bg-[var(--panel)] px-2 py-2">
        {tags.length ? (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {tags.map((tag, index) => (
              <span
                key={`${tag}-${index}`}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--line)] bg-[var(--accent-soft)] px-2 py-1 text-xs text-[var(--ink)]"
              >
                {tag}
                <button
                  type="button"
                  className="rounded px-0.5 text-[var(--muted)] hover:text-[var(--danger)]"
                  aria-label={`Remove ${tag}`}
                  onClick={() => removeTag(index)}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p className="mb-2 text-xs text-[var(--muted)]">No specs yet — e.g. 25mm, PVC, Grey</p>
        )}
        <div className="flex gap-2">
          <input
            className="h-9 min-w-0 flex-1 rounded-md border border-[var(--line)] bg-[var(--paper)] px-3 font-sans text-sm"
            placeholder="Type a spec and press Enter"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === ",") {
                event.preventDefault();
                addTag(draft);
              }
              if (event.key === "Backspace" && !draft && tags.length) {
                removeTag(tags.length - 1);
              }
            }}
          />
          <button
            type="button"
            className="h-9 rounded-md border border-[var(--line)] px-3 font-sans text-sm"
            onClick={() => addTag(draft)}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
};

const WizardProgress = ({ stepIndex }: { stepIndex: number }) => (
  <ol className="mt-6 flex flex-wrap gap-2 font-sans text-xs">
    {STEPS.map((step, index) => {
      const active = index === stepIndex;
      const done = index < stepIndex;
      return (
        <li
          key={step.id}
          className={[
            "flex items-center gap-2 rounded-full border px-3 py-1.5",
            active
              ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
              : done
                ? "border-[var(--line)] text-[var(--ink)]"
                : "border-[var(--line)] text-[var(--muted)]",
          ].join(" ")}
        >
          <span
            className={[
              "inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-medium",
              active || done ? "bg-[var(--accent)] text-[var(--on-accent)]" : "bg-[var(--paper)]",
            ].join(" ")}
          >
            {done ? "✓" : index + 1}
          </span>
          {step.title}
        </li>
      );
    })}
  </ol>
);

export const ProductCreatePage = () => {
  const navigate = useNavigate();
  const { push } = useToast();
  const [stepIndex, setStepIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<NamedRef[]>([]);
  const [brands, setBrands] = useState<NamedRef[]>([]);
  const [units, setUnits] = useState<UnitRef[]>([]);
  const [vendors, setVendors] = useState<NamedRef[]>([]);
  const [skuLocked, setSkuLocked] = useState(false);
  const [skuHint, setSkuHint] = useState("");
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const skuLockedRef = useRef(false);
  skuLockedRef.current = skuLocked;
  const [form, setForm] = useState<ProductForm>({
    name: "",
    sku: "",
    barcode: "",
    category: "",
    brand: "",
    unit: "",
    vendor: "",
    vendor_sku: "",
    specificationTags: [],
    hsn_code: "",
    alias_terms: "",
    min_stock_quantity: "0",
    reorder_level: "0",
  });

  useEffect(() => {
    void Promise.all([
      apiClient.get<Paginated<NamedRef>>("/categories/"),
      apiClient.get<Paginated<NamedRef>>("/brands/"),
      apiClient.get<Paginated<UnitRef>>("/units/"),
      apiClient.get<Paginated<NamedRef>>("/vendors/"),
    ]).then(([categoryPage, brandPage, unitPage, vendorPage]) => {
      setCategories(categoryPage.results);
      setBrands(brandPage.results);
      setUnits(unitPage.results);
      setVendors(vendorPage.results);
    });
  }, []);

  useEffect(() => {
    const name = form.name.trim();
    if (!name || skuLockedRef.current) {
      return;
    }
    const handle = window.setTimeout(() => {
      void apiClient
        .get<{ sku: string }>(`/products/suggest-sku/?name=${encodeURIComponent(name)}`)
        .then((payload) => {
          if (skuLockedRef.current) {
            return;
          }
          setForm((current) => (current.name.trim() === name ? { ...current, sku: payload.sku } : current));
          setSkuHint("Suggested from name · unique serial for this prefix");
        })
        .catch(() => null);
    }, 350);
    return () => window.clearTimeout(handle);
  }, [form.name]);

  const setField =
    (key: keyof ProductForm) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));

  const refreshSku = () => {
    const name = form.name.trim();
    if (!name) {
      push("error", "Name needed", "Enter a product name before generating a SKU.");
      return;
    }
    void apiClient
      .get<{ sku: string }>(`/products/suggest-sku/?name=${encodeURIComponent(name)}`)
      .then((payload) => {
        setForm((current) => ({ ...current, sku: payload.sku }));
        setSkuLocked(false);
        setSkuHint("Fresh unique suggestion");
      })
      .catch((err: unknown) => push("error", "SKU not generated", err instanceof Error ? err.message : "Request failed."));
  };

  const validateStep = (index: number): string | null => {
    if (index === 0) {
      if (!form.name.trim()) {
        return "Enter a product name.";
      }
      if (!form.sku.trim()) {
        return "SKU is required (use Suggest if needed).";
      }
    }
    if (index === 1) {
      if (!form.category) {
        return "Choose or add a category.";
      }
      if (!form.unit) {
        return "Choose a unit.";
      }
    }
    return null;
  };

  const goNext = () => {
    const problem = validateStep(stepIndex);
    if (problem) {
      push("error", "Almost there", problem);
      return;
    }
    setStepIndex((current) => Math.min(current + 1, STEPS.length - 1));
  };

  const goBack = () => setStepIndex((current) => Math.max(current - 1, 0));

  const save = () => {
    const identityProblem = validateStep(0);
    const classifyProblem = validateStep(1);
    if (identityProblem || classifyProblem) {
      push("error", "Missing fields", identityProblem || classifyProblem || "Check earlier steps.");
      return;
    }
    setSaving(true);
    void apiClient
      .post<{ id: number }>("/products/", {
        name: form.name,
        sku: form.sku.trim().toUpperCase(),
        barcode: form.barcode,
        category: Number(form.category),
        brand: form.brand ? Number(form.brand) : null,
        unit: Number(form.unit),
        specification: form.specificationTags.join(" · "),
        hsn_code: form.hsn_code,
        alias_terms: form.alias_terms
          .split(",")
          .map((term) => term.trim())
          .filter((term) => term.length > 0),
        min_stock_quantity: form.min_stock_quantity,
        reorder_level: form.reorder_level,
        is_active: true,
      })
      .then(async (product) => {
        if (pendingImage) {
          try {
            await apiClient.uploadProductImage(product.id, pendingImage);
          } catch (err: unknown) {
            push(
              "error",
              "Photo not saved",
              err instanceof Error ? err.message : "Product was created; add the photo from the product card.",
            );
          }
        }
        if (form.vendor) {
          await apiClient.post("/product-vendors/", {
            product: product.id,
            vendor: Number(form.vendor),
            vendor_sku: form.vendor_sku.trim(),
            is_preferred: true,
          });
        }
        push(
          "success",
          "Product created",
          form.vendor
            ? "Preferred vendor linked. Add opening stock on the Add stock tab."
            : "Add opening stock on the Add stock tab — quantity, cost, and selling price.",
        );
        navigate(`/inventory/${product.id}?tab=receive`);
      })
      .catch((err: unknown) => push("error", "Not saved", err instanceof Error ? err.message : "Request failed."))
      .finally(() => setSaving(false));
  };

  const categoryName = categories.find((row) => String(row.id) === form.category)?.name || "—";
  const brandName = brands.find((row) => String(row.id) === form.brand)?.name || "None";
  const vendorName = vendors.find((row) => String(row.id) === form.vendor)?.name || "None";
  const unitName =
    units.find((row) => String(row.id) === form.unit)?.abbreviation ||
    units.find((row) => String(row.id) === form.unit)?.name ||
    "—";
  const step = STEPS[stepIndex];
  const isLast = stepIndex === STEPS.length - 1;

  return (
    <section className="mx-auto max-w-2xl">
      <button
        type="button"
        className="font-sans text-sm text-[var(--muted)] underline-offset-2 hover:underline"
        onClick={() => navigate("/inventory")}
      >
        ← Back to inventory
      </button>
      <h2 className="mt-3 text-3xl">New product</h2>
      <p className="mt-2 font-sans text-sm text-[var(--muted)]">
        A short wizard for the catalog card only. Quantity in stock is added next, on the product’s{" "}
        <strong className="font-sans font-medium text-[var(--ink)]">Add stock</strong> tab (opening lot with cost and
        selling price). Use <strong className="font-sans font-medium text-[var(--ink)]">Supplier bills</strong> only when
        you have a vendor invoice to put on payables.
      </p>

      <WizardProgress stepIndex={stepIndex} />

      <div className="mt-6 rounded-xl border border-[var(--line)] bg-[var(--panel)] p-6 shadow-[var(--shadow)]">
        <p className="text-[11px] tracking-[0.18em] text-[var(--muted)] uppercase">
          Step {stepIndex + 1} of {STEPS.length}
        </p>
        <h3 className="mt-2 text-2xl">{step.title}</h3>
        <p className="mt-1 font-sans text-sm text-[var(--muted)]">{step.blurb}</p>

        <div className="mt-6 grid gap-4 font-sans text-sm">
          {step.id === "identity" ? (
            <>
              <label className="block">
                <FieldLabel hint="The name customers and staff will see on bills, search, and stock screens.">
                  Product name
                </FieldLabel>
                <input
                  autoFocus
                  value={form.name}
                  onChange={setField("name")}
                  className={fieldClass}
                  placeholder="Conduit Pipes"
                />
              </label>
              <label className="block">
                <FieldLabel hint="Stock Keeping Unit — your unique shop code. Auto-suggested from the name (e.g. Conduit Pipes → CP-00001). Must be unique.">
                  SKU
                </FieldLabel>
                <div className="mt-1 flex gap-2">
                  <input
                    value={form.sku}
                    onChange={(event) => {
                      setSkuLocked(true);
                      setSkuHint("Custom SKU — must stay unique");
                      setForm((current) => ({ ...current, sku: event.target.value.toUpperCase() }));
                    }}
                    className={`${fieldClass} mt-0`}
                    placeholder="CP-00001"
                  />
                  <button
                    type="button"
                    className="h-10 shrink-0 rounded-md border border-[var(--line)] px-3"
                    onClick={refreshSku}
                  >
                    Suggest
                  </button>
                </div>
                {skuHint ? <p className="mt-1 text-xs text-[var(--muted)]">{skuHint}</p> : null}
              </label>
              <label className="block">
                <FieldLabel hint="Optional manufacturer or shop barcode used with a scanner for quick lookup.">
                  Barcode (optional)
                </FieldLabel>
                <input value={form.barcode} onChange={setField("barcode")} className={fieldClass} placeholder="Scan or type" />
              </label>
            </>
          ) : null}

          {step.id === "classify" ? (
            <>
              <CreatableNamedSelect
                label="Category"
                hint="Groups similar products for browsing and reports (wires, switches, lighting…)."
                value={form.category}
                options={categories}
                createPath="/categories/"
                onChange={(category) => setForm((current) => ({ ...current, category }))}
                onCreated={(row) =>
                  setCategories((current) => [...current, row].sort((a, b) => a.name.localeCompare(b.name)))
                }
                onUpdated={(row) =>
                  setCategories((current) =>
                    current
                      .map((item) => (item.id === row.id ? row : item))
                      .sort((a, b) => a.name.localeCompare(b.name)),
                  )
                }
              />
              <CreatableNamedSelect
                label="Brand (optional)"
                hint="Manufacturer or house brand. Optional. Manage all brands under Catalog; select here then Rename for a quick fix."
                value={form.brand}
                options={brands}
                optional
                createPath="/brands/"
                onChange={(brand) => setForm((current) => ({ ...current, brand }))}
                onCreated={(row) => setBrands((current) => [...current, row].sort((a, b) => a.name.localeCompare(b.name)))}
                onUpdated={(row) =>
                  setBrands((current) =>
                    current
                      .map((item) => (item.id === row.id ? row : item))
                      .sort((a, b) => a.name.localeCompare(b.name)),
                  )
                }
              />
              <CreatableUnitSelect
                label="Unit"
                hint="How this item is counted in stock — metre, piece, box, kg, etc. Add a new unit if yours is missing."
                value={form.unit}
                options={units}
                onChange={(unit) => setForm((current) => ({ ...current, unit }))}
                onCreated={(row) => setUnits((current) => [...current, row].sort((a, b) => a.name.localeCompare(b.name)))}
              />
              <CreatableVendorSelect
                label="Preferred vendor (optional)"
                hint="Usual supplier for this item. Pick an existing vendor or add a new one. You can link more vendors later on the product card."
                value={form.vendor}
                options={vendors}
                onChange={(vendor) => setForm((current) => ({ ...current, vendor }))}
                onCreated={(row) => setVendors((current) => [...current, row].sort((a, b) => a.name.localeCompare(b.name)))}
              />
              {form.vendor ? (
                <label className="block">
                  <FieldLabel hint="Optional code this supplier uses for the same item on their invoice or price list.">
                    Vendor SKU (optional)
                  </FieldLabel>
                  <input
                    value={form.vendor_sku}
                    onChange={setField("vendor_sku")}
                    className={fieldClass}
                    placeholder="Supplier’s item code"
                  />
                </label>
              ) : null}
            </>
          ) : null}

          {step.id === "details" ? (
            <>
              <SpecTagsField
                tags={form.specificationTags}
                onChange={(specificationTags) => setForm((current) => ({ ...current, specificationTags }))}
              />
              <label className="block">
                <FieldLabel hint="GST Harmonised System of Nomenclature code for tax invoices. Leave blank if not needed.">
                  HSN code (optional)
                </FieldLabel>
                <input value={form.hsn_code} onChange={setField("hsn_code")} className={fieldClass} />
              </label>
              <label className="block">
                <FieldLabel hint="Extra search words (comma separated) so Smart Finder matches shop slang — e.g. PVC pipe, conduit.">
                  Search aliases (optional)
                </FieldLabel>
                <input
                  value={form.alias_terms}
                  onChange={setField("alias_terms")}
                  className={fieldClass}
                  placeholder="Comma separated — e.g. PVC pipe, conduit"
                />
              </label>
            </>
          ) : null}

          {step.id === "stock" ? (
            <>
              <ProductImageField pendingFile={pendingImage} onPendingFile={setPendingImage} />
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <FieldLabel hint="When on-hand stock falls to this quantity or below, the item is treated as low stock.">
                    Minimum stock
                  </FieldLabel>
                  <input value={form.min_stock_quantity} onChange={setField("min_stock_quantity")} className={fieldClass} />
                </label>
                <label className="block">
                  <FieldLabel hint="Suggested level at which you should reorder from the vendor. Often equal to or above minimum stock.">
                    Reorder level
                  </FieldLabel>
                  <input value={form.reorder_level} onChange={setField("reorder_level")} className={fieldClass} />
                </label>
              </div>
              <div className="rounded-lg border border-[var(--line)] bg-[var(--paper)] p-4">
                <p className="text-xs tracking-wide text-[var(--muted)] uppercase">Review</p>
                <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                  {[
                    ["Name", form.name || "—"],
                    ["SKU", form.sku || "—"],
                    ["Barcode", form.barcode || "—"],
                    ["Category", categoryName],
                    ["Brand", brandName],
                    ["Unit", unitName],
                    ["Preferred vendor", vendorName],
                    ["HSN", form.hsn_code || "—"],
                    ["Min / reorder", `${form.min_stock_quantity} / ${form.reorder_level}`],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-xs text-[var(--muted)]">{label}</dt>
                      <dd className="mt-0.5">{value}</dd>
                    </div>
                  ))}
                </dl>
                {form.specificationTags.length ? (
                  <div className="mt-3 flex flex-wrap gap-1.5 border-t border-[var(--line)] pt-3">
                    {form.specificationTags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md border border-[var(--line)] bg-[var(--accent-soft)] px-2 py-1 text-xs"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </>
          ) : null}
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            className="h-10 rounded-md border border-[var(--line)] px-4 font-sans text-sm disabled:opacity-40"
            onClick={goBack}
            disabled={stepIndex === 0 || saving}
          >
            Back
          </button>
          {!isLast ? (
            <button
              type="button"
              className="h-10 rounded-md bg-[var(--accent)] px-5 font-sans text-sm text-[var(--on-accent)]"
              onClick={goNext}
            >
              Continue
            </button>
          ) : (
            <button
              type="button"
              disabled={saving}
              className="h-10 rounded-md bg-[var(--accent)] px-5 font-sans text-sm text-[var(--on-accent)] disabled:opacity-60"
              onClick={save}
            >
              {saving ? "Saving…" : "Create product"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
};
