import { useEffect, useState } from "react";
import { apiClient, type Paginated } from "../services/api.ts";
import { formatMoney, sanitizeDecimalInput } from "../utils/money.ts";

type Party = { id: number; name: string; phone: string; gstin: string; current_balance: string; is_active: boolean };

type CustomerType = { id: number; code: string; name: string; is_active: boolean };

type CustomerRow = Party & {
  alternate_phone: string;
  address: string;
  customer_type: number | null;
  customer_type_name: string | null;
  credit_limit: string;
  notes: string;
  loyalty_points: number;
};

type VendorRow = Party & {
  email: string;
  address: string;
  alternate_phone: string;
  contact_person: string;
};

const loadVendors = (setRows: (rows: VendorRow[]) => void) => {
  void apiClient.get<Paginated<VendorRow>>("/vendors/").then((page) => setRows(page.results));
};

const fieldClass = "h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm";

const emptyCustomerForm = {
  name: "",
  phone: "",
  alternate_phone: "",
  customer_type: "",
  gstin: "",
  address: "",
  credit_limit: "0.00",
  notes: "",
};

export const CustomersPage = () => {
  const [rows, setRows] = useState<CustomerRow[]>([]);
  const [types, setTypes] = useState<CustomerType[]>([]);
  const [form, setForm] = useState(emptyCustomerForm);
  const [filter, setFilter] = useState("");

  const reload = () => {
    void apiClient.get<Paginated<CustomerRow>>("/customers/").then((page) => setRows(page.results));
  };

  useEffect(() => {
    reload();
    void apiClient
      .get<Paginated<CustomerType>>("/customer-types/?is_active=true")
      .then((page) => setTypes(page.results));
  }, []);

  const setField = (key: keyof typeof emptyCustomerForm) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const visible = rows.filter((row) => {
    const q = filter.trim().toLowerCase();
    if (!q) return true;
    return [row.name, row.phone, row.alternate_phone, row.customer_type_name || "", row.gstin, row.notes]
      .join(" ")
      .toLowerCase()
      .includes(q);
  });

  return (
    <section>
      <h2 className="text-3xl">Customers</h2>
      <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
        Save name, mobile, and type (Electrician, General, …) so bills link to the right buyer. Mobile is the main
        identifier for returning customers and frequent-buyer analytics. Loyalty points are reserved for a later stage.
      </p>
      <form
        className="mt-6 grid max-w-2xl gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void apiClient
            .post("/customers/", {
              name: form.name.trim(),
              phone: form.phone.trim(),
              alternate_phone: form.alternate_phone.trim(),
              customer_type: form.customer_type ? Number(form.customer_type) : null,
              gstin: form.gstin.trim(),
              address: form.address.trim(),
              credit_limit: form.credit_limit || "0",
              notes: form.notes.trim(),
            })
            .then(() => {
              reload();
              setForm(emptyCustomerForm);
            });
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block font-sans text-sm sm:col-span-2">
            <span className="text-[var(--muted)]">Name</span>
            <input className={`${fieldClass} mt-1`} required value={form.name} onChange={setField("name")} placeholder="Required" />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Mobile (recommended)</span>
            <input
              className={`${fieldClass} mt-1`}
              value={form.phone}
              onChange={setField("phone")}
              placeholder="Primary number to find them later"
              inputMode="tel"
            />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Alternate phone</span>
            <input className={`${fieldClass} mt-1`} value={form.alternate_phone} onChange={setField("alternate_phone")} inputMode="tel" />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Customer type</span>
            <select className={`${fieldClass} mt-1`} value={form.customer_type} onChange={setField("customer_type")}>
              <option value="">General (default)</option>
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Credit limit (₹)</span>
            <input
              className={`${fieldClass} mt-1`}
              value={form.credit_limit}
              onChange={(e) => setForm((c) => ({ ...c, credit_limit: sanitizeDecimalInput(e.target.value, 2) }))}
            />
          </label>
        </div>
        <label className="block font-sans text-sm">
          <span className="text-[var(--muted)]">GSTIN (optional)</span>
          <input className={`${fieldClass} mt-1`} value={form.gstin} onChange={setField("gstin")} />
        </label>
        <label className="block font-sans text-sm">
          <span className="text-[var(--muted)]">Address (optional)</span>
          <textarea
            className={`${fieldClass} mt-1 min-h-20 py-2`}
            value={form.address}
            onChange={setField("address")}
            placeholder="Area, landmark, city"
          />
        </label>
        <label className="block font-sans text-sm">
          <span className="text-[var(--muted)]">Notes (optional)</span>
          <textarea
            className={`${fieldClass} mt-1 min-h-16 py-2`}
            value={form.notes}
            onChange={setField("notes")}
            placeholder="Site name, preferred discount, etc."
          />
        </label>
        <button className="h-10 w-fit rounded-md bg-[var(--accent)] px-4 font-sans text-sm text-[var(--on-accent)]" type="submit">
          Save customer
        </button>
      </form>

      <div className="mt-8 flex flex-wrap items-end justify-between gap-3">
        <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Directory</p>
        <input
          className="h-10 w-full max-w-xs rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name, mobile, type…"
        />
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[44rem] font-sans text-sm">
          <thead>
            <tr className="text-left text-[var(--muted)]">
              <th className="py-2">Name</th>
              <th>Type</th>
              <th>Mobile</th>
              <th>Address</th>
              <th>Balance</th>
              <th>Points</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id} className="border-t border-[var(--line)] align-top">
                <td className="py-2">
                  <div>{row.name}</div>
                  {row.gstin ? <div className="text-xs text-[var(--muted)]">{row.gstin}</div> : null}
                  {row.notes ? <div className="text-xs text-[var(--muted)]">{row.notes}</div> : null}
                </td>
                <td className="py-2">{row.customer_type_name || "General"}</td>
                <td className="py-2">
                  <div>{row.phone || "—"}</div>
                  {row.alternate_phone ? <div className="text-xs text-[var(--muted)]">{row.alternate_phone}</div> : null}
                </td>
                <td className="max-w-xs py-2 whitespace-pre-wrap">{row.address || "—"}</td>
                <td className="py-2">{formatMoney(row.current_balance)}</td>
                <td className="py-2 text-[var(--muted)]">{row.loyalty_points ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

const emptyVendorForm = {
  name: "",
  contact_person: "",
  phone: "",
  alternate_phone: "",
  email: "",
  gstin: "",
  address: "",
};

export const VendorsPage = () => {
  const [rows, setRows] = useState<VendorRow[]>([]);
  const [form, setForm] = useState(emptyVendorForm);

  useEffect(() => {
    loadVendors(setRows);
  }, []);

  const setField = (key: keyof typeof emptyVendorForm) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <section>
      <h2 className="text-3xl">Vendors</h2>
      <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
        Supplier name is required. Address and contact details are optional and can be filled in later.
      </p>
      <form
        className="mt-6 grid max-w-2xl gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void apiClient
            .post("/vendors/", {
              name: form.name.trim(),
              contact_person: form.contact_person.trim(),
              phone: form.phone.trim(),
              alternate_phone: form.alternate_phone.trim(),
              email: form.email.trim(),
              gstin: form.gstin.trim(),
              address: form.address.trim(),
            })
            .then(() => {
              loadVendors(setRows);
              setForm(emptyVendorForm);
            });
        }}
      >
        <label className="block font-sans text-sm">
          <span className="text-[var(--muted)]">Supplier name</span>
          <input className={`${fieldClass} mt-1`} required value={form.name} onChange={setField("name")} placeholder="Required" />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Contact person (optional)</span>
            <input className={`${fieldClass} mt-1`} value={form.contact_person} onChange={setField("contact_person")} />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Phone (optional)</span>
            <input className={`${fieldClass} mt-1`} value={form.phone} onChange={setField("phone")} />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Alternate phone (optional)</span>
            <input className={`${fieldClass} mt-1`} value={form.alternate_phone} onChange={setField("alternate_phone")} />
          </label>
          <label className="block font-sans text-sm">
            <span className="text-[var(--muted)]">Email (optional)</span>
            <input className={`${fieldClass} mt-1`} type="email" value={form.email} onChange={setField("email")} />
          </label>
        </div>
        <label className="block font-sans text-sm">
          <span className="text-[var(--muted)]">GSTIN (optional)</span>
          <input className={`${fieldClass} mt-1`} value={form.gstin} onChange={setField("gstin")} />
        </label>
        <label className="block font-sans text-sm">
          <span className="text-[var(--muted)]">Address (optional)</span>
          <textarea
            className={`${fieldClass} mt-1 min-h-20 py-2`}
            value={form.address}
            onChange={setField("address")}
            placeholder="Street, city, pin"
          />
        </label>
        <button className="h-10 w-fit rounded-md bg-[var(--accent)] px-4 font-sans text-sm text-[var(--on-accent)]" type="submit">
          Save vendor
        </button>
      </form>
      <div className="mt-8 overflow-x-auto">
        <table className="w-full min-w-[40rem] font-sans text-sm">
          <thead>
            <tr className="text-left text-[var(--muted)]">
              <th className="py-2">Name</th>
              <th>Contact</th>
              <th>Phone</th>
              <th>Address</th>
              <th>Payable</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-[var(--line)] align-top">
                <td className="py-2">
                  <div>{row.name}</div>
                  {row.gstin ? <div className="text-xs text-[var(--muted)]">{row.gstin}</div> : null}
                </td>
                <td className="py-2">
                  <div>{row.contact_person || "—"}</div>
                  {row.email ? <div className="text-xs text-[var(--muted)]">{row.email}</div> : null}
                </td>
                <td className="py-2">
                  <div>{row.phone || "—"}</div>
                  {row.alternate_phone ? <div className="text-xs text-[var(--muted)]">{row.alternate_phone}</div> : null}
                </td>
                <td className="max-w-xs py-2 whitespace-pre-wrap">{row.address || "—"}</td>
                <td className="py-2">{formatMoney(row.current_balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
