import { useEffect, useMemo, useState } from "react";
import { useToast } from "../hooks/useToast.ts";
import { apiClient, type FinderRow, type Paginated, type ProductCard } from "../services/api.ts";
import { formatMoney, sanitizeDecimalInput } from "../utils/money.ts";
import { printHtmlDocument } from "../utils/printHtml.ts";

type Customer = {
  id: number;
  name: string;
  phone?: string;
  customer_type?: number | null;
  customer_type_name?: string | null;
};
type CustomerType = { id: number; code: string; name: string };

/**
 * One bill line at the counter.
 * list_price = catalog selling price; bill_price = what the customer is charged (may be discounted).
 * Cost / safe / max discount stay internal for margin checks; billing UI shows MRP not purchase cost.
 * MRP can appear on the customer invoice when the lot has one.
 * batch_id selects which open lot to sell from; prices follow that lot.
 */
type OpenLot = {
  id: number;
  lot_code: string;
  vendor_name: string;
  purchase_date: string;
  remaining_quantity: string;
  purchase_cost: string;
  selling_price: string;
  safe_selling_price: string;
  mrp: string;
  maximum_discount_percent: string;
};

type BillLine = {
  product_id: number;
  sku: string;
  name: string;
  specification: string;
  quantity: string;
  list_price: string;
  bill_price: string;
  cost_price: string;
  safe_selling_price: string;
  mrp: string;
  max_discount_percent: string;
  stock: string;
  next_lot_code: string;
  latest_selling_price: string;
  price_note: string;
  batch_id: number | null;
  lots: OpenLot[];
  below_safe_override: boolean;
};

type InvoiceItem = {
  name?: string;
  specification?: string;
  quantity?: string;
  unit_price?: string;
  mrp?: string;
  discount?: string;
  line_total?: string;
};

type SaleDetailItem = {
  id: number;
  product: number;
  sku: string;
  product_name: string;
  specification?: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  resulting_price: string;
  batch_cost: string;
};

type SaleDetail = {
  id: number;
  customer: number | null;
  invoice_number: string;
  payment_method: string;
  amount_paid: string;
  amount_tendered: string;
  change_given: string;
  payment_reference: string;
  items: SaleDetailItem[];
};

const fieldClass = "h-10 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 font-sans text-sm";

const moneyOrZero = (value: string | null | undefined) => formatMoney(value ?? "0");

/** Signed vs list: positive = discount (bill below list), negative = markup (bill above list). */
const listDeltaPercent = (list: number, bill: number) => {
  if (!list || bill === list) return 0;
  return ((list - bill) / list) * 100;
};

/** Absolute discount % used for API when bill is below list. */
const discountPercentOf = (list: number, bill: number) => Math.max(0, listDeltaPercent(list, bill));

/**
 * Counter billing — shopkeeper sees list vs bill price and selling range;
 * completed / printed invoice shows only customer-facing totals.
 */
export const SalesPage = () => {
  const { push } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<FinderRow[]>([]);
  const [lines, setLines] = useState<BillLine[]>([]);
  const [method, setMethod] = useState("CASH");
  const [paid, setPaid] = useState("");
  const [paidTouched, setPaidTouched] = useState(false);
  const [tendered, setTendered] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [warning, setWarning] = useState("");
  const [busy, setBusy] = useState(false);
  const [invoice, setInvoice] = useState<Record<string, unknown> | null>(null);
  const [saleId, setSaleId] = useState<number | null>(null);
  /** When set, Complete/Update posts to /sales/{id}/revise/ instead of create. */
  const [editingSaleId, setEditingSaleId] = useState<number | null>(null);
  const [editingInvoiceNumber, setEditingInvoiceNumber] = useState("");
  const [addingCustomer, setAddingCustomer] = useState(false);
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newCustomerPhone, setNewCustomerPhone] = useState("");
  const [newCustomerType, setNewCustomerType] = useState("");
  const [customerTypes, setCustomerTypes] = useState<CustomerType[]>([]);
  const [customerLookup, setCustomerLookup] = useState("");
  const [customerHits, setCustomerHits] = useState<Customer[]>([]);
  /** Product ids whose shopkeeper price range is expanded on the bill. */
  const [priceDetailOpen, setPriceDetailOpen] = useState<Record<number, boolean>>({});

  const reloadCustomers = () => {
    void apiClient.get<Paginated<Customer>>("/customers/").then((page) => setCustomers(page.results));
  };

  useEffect(() => {
    reloadCustomers();
    void apiClient
      .get<Paginated<CustomerType>>("/customer-types/?is_active=true")
      .then((page) => setCustomerTypes(page.results));
  }, []);

  useEffect(() => {
    if (!customerLookup.trim()) {
      setCustomerHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void apiClient
        .get<Customer[]>(`/customers/lookup/?q=${encodeURIComponent(customerLookup.trim())}`)
        .then((rows) => setCustomerHits(rows));
    }, 120);
    return () => window.clearTimeout(handle);
  }, [customerLookup]);

  useEffect(() => {
    if (!query.trim()) {
      setHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void apiClient
        .get<Paginated<FinderRow>>(`/products/finder/?q=${encodeURIComponent(query)}`)
        .then((page) => setHits(page.results));
    }, 80);
    return () => window.clearTimeout(handle);
  }, [query]);

  const billTotals = useMemo(() => {
    return lines.reduce(
      (acc, line) => {
        const qty = Number(line.quantity) || 0;
        const list = Number(line.list_price) || 0;
        const bill = Number(line.bill_price) || 0;
        const mrp = Number(line.mrp) || 0;
        // Payment panel uses MRP when set; otherwise falls back to list (sell) for that line.
        const reference = mrp > 0 ? mrp : list;
        const lineList = qty * list;
        const lineMrp = qty * reference;
        const lineBill = qty * bill;
        const lineDisc = Math.max(0, lineList - lineBill);
        const lineMrpDisc = Math.max(0, lineMrp - lineBill);
        return {
          listSubtotal: acc.listSubtotal + lineList,
          mrpSubtotal: acc.mrpSubtotal + lineMrp,
          billTotal: acc.billTotal + lineBill,
          discountTotal: acc.discountTotal + lineDisc,
          mrpDiscountTotal: acc.mrpDiscountTotal + lineMrpDisc,
        };
      },
      { listSubtotal: 0, mrpSubtotal: 0, billTotal: 0, discountTotal: 0, mrpDiscountTotal: 0 },
    );
  }, [lines]);

  const hasMrpOnBill = lines.some((line) => Number(line.mrp) > 0);
  const referenceSubtotal = hasMrpOnBill ? billTotals.mrpSubtotal : billTotals.listSubtotal;
  const referenceDiscount = hasMrpOnBill ? billTotals.mrpDiscountTotal : billTotals.discountTotal;
  const referenceSubtotalLabel = hasMrpOnBill ? "MRP subtotal" : "List subtotal";

  const grandTotal = billTotals.billTotal;
  const cashGiven = Number(tendered) || 0;
  const changeDue = method === "CASH" ? Math.max(0, cashGiven - grandTotal) : 0;
  const cashShort = method === "CASH" && cashGiven > 0 && cashGiven < grandTotal;

  useEffect(() => {
    if (!paidTouched) {
      if (method === "CREDIT") {
        setPaid("0.00");
      } else if (method === "CASH" && cashGiven > 0 && cashGiven < grandTotal) {
        setPaid(formatMoney(cashGiven));
      } else {
        setPaid(formatMoney(grandTotal));
      }
    }
  }, [grandTotal, paidTouched, method, cashGiven]);

  const amountDue = Math.max(0, grandTotal - (Number(paid) || 0));

  const addLine = (hit: FinderRow) => {
    // Default list/bill = next FIFO lot (stock that leaves first). Latest is shown if different.
    const list = moneyOrZero(hit.active_selling_price);
    const latest = moneyOrZero(hit.latest_selling_price);
    const lotsDiffer =
      hit.latest_selling_price != null &&
      hit.active_selling_price != null &&
      formatMoney(hit.latest_selling_price) !== formatMoney(hit.active_selling_price);
    const baseNote = lotsDiffer
      ? `Bill uses next lot ${hit.next_lot_code || ""} (₹${list}). Newest lot ${hit.latest_lot_code || ""} is ₹${latest}.`
      : hit.next_lot_code
        ? `Next lot ${hit.next_lot_code}`
        : "";

    const applyNewLine = (lots: OpenLot[]) => {
      const fifoLot = lots[0] ?? null;
      setLines((current) => {
        const existing = current.findIndex((row) => row.product_id === hit.id);
        if (existing >= 0) {
          return current.map((row, index) =>
            index === existing ? { ...row, quantity: formatMoney(Number(row.quantity) + 1) } : row,
          );
        }
        const sell = fifoLot ? moneyOrZero(fifoLot.selling_price) : list;
        return [
          ...current,
          {
            product_id: hit.id,
            sku: hit.sku,
            name: hit.name,
            specification: hit.specification || "",
            quantity: "1.00",
            list_price: sell,
            bill_price: sell,
            cost_price: fifoLot ? moneyOrZero(fifoLot.purchase_cost) : moneyOrZero(hit.active_cost),
            safe_selling_price: fifoLot
              ? moneyOrZero(fifoLot.safe_selling_price)
              : moneyOrZero(hit.active_safe_selling_price),
            mrp: fifoLot ? moneyOrZero(fifoLot.mrp) : moneyOrZero(hit.active_mrp),
            max_discount_percent: fifoLot
              ? moneyOrZero(fifoLot.maximum_discount_percent)
              : moneyOrZero(hit.active_max_discount),
            stock: formatMoney(hit.current_stock),
            next_lot_code: fifoLot?.lot_code || hit.next_lot_code || "",
            latest_selling_price: latest,
            price_note: fifoLot
              ? `Lot ${fifoLot.lot_code} · sell ₹${sell} · ${formatMoney(fifoLot.remaining_quantity)} left`
              : baseNote,
            // Pre-select next FIFO lot so the dropdown drives prices immediately.
            batch_id: fifoLot ? fifoLot.id : null,
            lots,
            below_safe_override: false,
          },
        ];
      });
    };

    void apiClient
      .get<OpenLot[]>(`/products/${hit.id}/open-lots/`)
      .then((lots) => applyNewLine(lots))
      .catch(() => applyNewLine([]));
    setQuery("");
    setHits([]);
  };

  const selectLot = (index: number, batchId: number) => {
    setLines((rows) =>
      rows.map((row, i) => {
        if (i !== index) return row;
        const lot = row.lots.find((item) => item.id === batchId);
        if (!lot) return row;
        const sell = moneyOrZero(lot.selling_price);
        return {
          ...row,
          batch_id: lot.id,
          list_price: sell,
          bill_price: sell,
          cost_price: moneyOrZero(lot.purchase_cost),
          safe_selling_price: moneyOrZero(lot.safe_selling_price),
          mrp: moneyOrZero(lot.mrp),
          max_discount_percent: moneyOrZero(lot.maximum_discount_percent),
          next_lot_code: lot.lot_code,
          price_note: `Lot ${lot.lot_code}${lot.vendor_name ? ` · ${lot.vendor_name}` : ""} · sell ₹${sell}${Number(lot.mrp) > 0 ? ` · MRP ₹${moneyOrZero(lot.mrp)}` : ""} · ${formatMoney(lot.remaining_quantity)} left`,
        };
      }),
    );
  };

  const updateLine = (index: number, patch: Partial<BillLine>) => {
    setLines((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const removeLine = (index: number) => {
    setLines((rows) => rows.filter((_, i) => i !== index));
  };

  const createCustomer = () => {
    const name = newCustomerName.trim();
    if (!name) {
      push("error", "Name needed", "Enter a customer name.");
      return;
    }
    if (!newCustomerPhone.trim()) {
      push("error", "Mobile needed", "Add a mobile number so you can find this customer on the next visit.");
      return;
    }
    void apiClient
      .post<Customer>("/customers/", {
        name,
        phone: newCustomerPhone.trim(),
        customer_type: newCustomerType ? Number(newCustomerType) : null,
      })
      .then((row) => {
        reloadCustomers();
        setCustomerId(String(row.id));
        setAddingCustomer(false);
        setNewCustomerName("");
        setNewCustomerPhone("");
        setNewCustomerType("");
        setCustomerLookup("");
        setCustomerHits([]);
        push("success", "Customer added", `${row.name} selected on this bill.`);
      })
      .catch((err: unknown) => push("error", "Not saved", err instanceof Error ? err.message : "Request failed."));
  };

  const selectCustomer = (row: Customer) => {
    setCustomerId(String(row.id));
    setCustomerLookup("");
    setCustomerHits([]);
  };

  const selectedCustomer = customers.find((row) => String(row.id) === customerId);

  /** Build API payload: list as unit_price, line discount when bill < list. */
  const buildSaleItems = (override: boolean) =>
    lines.map((line) => {
      const qty = Number(line.quantity) || 0;
      const list = Number(line.list_price) || 0;
      const bill = Number(line.bill_price) || 0;
      const unitPrice = bill > list ? bill : list;
      const discountAmount = bill < list ? Math.max(0, (list - bill) * qty) : 0;
      const discPct = discountPercentOf(list, Math.min(bill, list));
      return {
        product_id: line.product_id,
        quantity: line.quantity,
        unit_price: formatMoney(unitPrice),
        discount_amount: formatMoney(discountAmount),
        discount_percent: formatMoney(discPct),
        below_safe_override: override || line.below_safe_override,
        ...(line.batch_id ? { batch_id: line.batch_id } : {}),
      };
    });

  const buildPaymentBody = (override: boolean) => {
    const body: Record<string, unknown> = {
      customer_id: customerId ? Number(customerId) : null,
      payment_method: method,
      items: buildSaleItems(override),
    };
    if (method === "CASH") {
      body.amount_tendered = tendered || "0";
      // Full cash: omit amount_paid so server treats the bill as settled and computes change.
      if (cashGiven > 0 && cashGiven < grandTotal) {
        body.amount_paid = formatMoney(cashGiven);
      } else if (paidTouched) {
        body.amount_paid = paid || "0";
      }
    } else if (method === "CREDIT") {
      body.amount_paid = "0";
    } else {
      body.amount_paid = paid || formatMoney(grandTotal);
      if (paymentReference.trim()) {
        body.payment_reference = paymentReference.trim();
      }
    }
    return body;
  };

  const post = (override: boolean) => {
    if (!lines.length) {
      setWarning("Add at least one item to the bill.");
      return;
    }
    if (method === "CREDIT" && !customerId) {
      setWarning("Credit sales need a customer — pick one or add a new customer.");
      return;
    }
    if (method === "CASH" && !tendered.trim()) {
      setWarning("Enter cash given so change can be calculated.");
      return;
    }
    setBusy(true);
    setWarning("");
    const body = buildPaymentBody(override);
    const revisingId = editingSaleId;
    const request = revisingId
      ? apiClient.post<{ id: number }>(`/sales/${revisingId}/revise/`, body)
      : apiClient.post<{ id: number }>("/sales/", body);
    void request
      .then((sale) => {
        setSaleId(sale.id);
        setEditingSaleId(null);
        setEditingInvoiceNumber("");
        return apiClient.get<Record<string, unknown>>(`/sales/${sale.id}/invoice/`);
      })
      .then((payload) => {
        setInvoice(payload);
        setLines([]);
        setPaidTouched(false);
        setPaid("0.00");
        setTendered("");
        setPaymentReference("");
        setWarning("");
        push(
          "success",
          revisingId ? "Sale updated" : "Sale completed",
          `Invoice ${String(payload.invoice_number)} is ready.`,
        );
      })
      .catch((error: unknown) => setWarning(error instanceof Error ? error.message : "Sale failed"))
      .finally(() => setBusy(false));
  };

  const editLastBill = () => {
    if (!saleId) return;
    setBusy(true);
    setWarning("");
    void apiClient
      .get<SaleDetail>(`/sales/${saleId}/`)
      .then(async (sale) => {
        const grouped = new Map<
          number,
          { qty: number; list: number; bill: number; name: string; sku: string; specification: string }
        >();
        sale.items.forEach((item) => {
          const current = grouped.get(item.product);
          const qty = Number(item.quantity) || 0;
          const list = Number(item.unit_price) || 0;
          const bill = Number(item.resulting_price) || list;
          if (current) {
            current.qty += qty;
          } else {
            grouped.set(item.product, {
              qty,
              list,
              bill,
              name: item.product_name,
              sku: item.sku,
              specification: item.specification || "",
            });
          }
        });
        const nextLines: BillLine[] = [];
        for (const [productId, row] of grouped) {
          const card = await apiClient.get<ProductCard>(`/products/${productId}/card/`);
          const pricing = card.pricing;
          nextLines.push({
            product_id: productId,
            sku: row.sku,
            name: row.name,
            specification: row.specification || card.product.specification || "",
            quantity: formatMoney(row.qty),
            list_price: formatMoney(row.list),
            bill_price: formatMoney(row.bill),
            cost_price: moneyOrZero(pricing?.current_cost ?? "0"),
            safe_selling_price: moneyOrZero(pricing?.safe_selling_price ?? "0"),
            mrp: moneyOrZero(pricing?.mrp ?? "0"),
            max_discount_percent: moneyOrZero(pricing?.maximum_discount_percent ?? "0"),
            stock: formatMoney(card.stock.on_hand),
            next_lot_code: pricing?.lot_code || "",
            latest_selling_price: moneyOrZero(card.pricing_latest?.selling_price ?? pricing?.selling_price ?? "0"),
            price_note: "",
            batch_id: null,
            lots: [],
            below_safe_override: false,
          });
          try {
            const lots = await apiClient.get<OpenLot[]>(`/products/${productId}/open-lots/`);
            const last = nextLines[nextLines.length - 1];
            if (last) {
              last.lots = lots;
              const match =
                lots.find((lot) => formatMoney(lot.selling_price) === formatMoney(row.list)) ?? lots[0];
              if (match) {
                last.batch_id = match.id;
                last.next_lot_code = match.lot_code;
                last.list_price = moneyOrZero(match.selling_price);
                last.bill_price = formatMoney(row.bill);
                last.cost_price = moneyOrZero(match.purchase_cost);
                last.safe_selling_price = moneyOrZero(match.safe_selling_price);
                last.mrp = moneyOrZero(match.mrp);
                last.max_discount_percent = moneyOrZero(match.maximum_discount_percent);
              }
            }
          } catch {
            /* lots optional when editing */
          }
        }
        setLines(nextLines);
        setCustomerId(sale.customer ? String(sale.customer) : "");
        setMethod(sale.payment_method || "CASH");
        setTendered(sale.amount_tendered && Number(sale.amount_tendered) > 0 ? formatMoney(sale.amount_tendered) : "");
        setPaymentReference(sale.payment_reference || "");
        setPaid(formatMoney(sale.amount_paid));
        setPaidTouched(true);
        setEditingSaleId(sale.id);
        setEditingInvoiceNumber(sale.invoice_number);
        setInvoice(null);
        push("success", "Editing bill", `${sale.invoice_number} is open for changes. Update sale when done.`);
      })
      .catch((error: unknown) => setWarning(error instanceof Error ? error.message : "Could not load sale"))
      .finally(() => setBusy(false));
  };

  const printInvoice = () => {
    if (!saleId) {
      window.print();
      return;
    }
    void apiClient
      .get<{ html: string }>(`/sales/${saleId}/print/?kind=a4`)
      .then((payload) => printHtmlDocument(payload.html))
      .catch((error: unknown) => setWarning(error instanceof Error ? error.message : "Could not print invoice"));
  };

  const newBill = () => {
    setInvoice(null);
    setSaleId(null);
    setEditingSaleId(null);
    setEditingInvoiceNumber("");
    setLines([]);
    setWarning("");
    setPaidTouched(false);
    setPaid("0.00");
    setTendered("");
    setPaymentReference("");
    setQuery("");
  };

  const invoiceItems = (invoice?.items as InvoiceItem[] | undefined) ?? [];
  const invoiceHasDiscount = Number(invoice?.discount_amount ?? 0) > 0;
  const invoiceHasMrp = invoiceItems.some((item) => Number(item.mrp ?? 0) > 0);

  return (
    <section className="w-full">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl">Bill / Counter sale</h2>
          <p className="mt-2 max-w-3xl font-sans text-sm text-[var(--muted)]">
            Enter a discounted bill price when a customer asks. Default list price is the{" "}
            <strong className="font-sans font-medium text-[var(--ink)]">next lot sold (FIFO)</strong> — not always the
            newest restock. You can raise the bill price to the newest lot’s price when needed.
          </p>
        </div>
        {invoice ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={editLastBill} disabled={busy}>
              Edit bill
            </button>
            <button type="button" onClick={newBill}>
              New bill
            </button>
          </div>
        ) : null}
      </div>

      {editingSaleId ? (
        <p className="mt-4 rounded-md border border-[var(--warn-line)] bg-[var(--warn-bg)] px-3 py-2 font-sans text-sm text-[var(--warn-ink)]">
          Editing invoice {editingInvoiceNumber}. Change items or payment, then tap Update sale. Same invoice number is
          kept.
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0 space-y-4">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[var(--shadow)]">
            <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Customer</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
              <select className={fieldClass} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                <option value="">Walk-in (no ledger)</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                    {customer.phone ? ` · ${customer.phone}` : ""}
                    {customer.customer_type_name ? ` · ${customer.customer_type_name}` : ""}
                  </option>
                ))}
              </select>
              <button type="button" onClick={() => setAddingCustomer((open) => !open)}>
                {addingCustomer ? "Cancel" : "+ Customer"}
              </button>
            </div>
            <label className="mt-3 block font-sans text-sm">
              <span className="text-xs text-[var(--muted)]">Find by mobile or name</span>
              <input
                className={`${fieldClass} mt-1`}
                value={customerLookup}
                onChange={(e) => setCustomerLookup(e.target.value)}
                placeholder="Type mobile number or name…"
                inputMode="tel"
              />
            </label>
            {customerHits.length ? (
              <ul className="mt-2 max-h-40 overflow-y-auto rounded-md border border-[var(--line)]">
                {customerHits.map((hit) => (
                  <li key={hit.id}>
                    <button
                      type="button"
                      className="flex w-full justify-between gap-3 rounded-none border-0 border-b border-[var(--line)] px-3 py-2 text-left shadow-none last:border-b-0"
                      onClick={() => selectCustomer(hit)}
                    >
                      <span>
                        <span className="font-medium">{hit.name}</span>
                        <span className="mt-0.5 block text-xs text-[var(--muted)]">
                          {hit.customer_type_name || "General"}
                          {hit.phone ? ` · ${hit.phone}` : ""}
                        </span>
                      </span>
                      <span className="text-xs text-[var(--muted)]">Select</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {selectedCustomer ? (
              <p className="mt-2 font-sans text-xs text-[var(--muted)]">
                Linked: {selectedCustomer.name}
                {selectedCustomer.phone ? ` · ${selectedCustomer.phone}` : " · no mobile on file"}
                {selectedCustomer.customer_type_name ? ` · ${selectedCustomer.customer_type_name}` : ""}
              </p>
            ) : (
              <p className="mt-2 font-sans text-xs text-[var(--muted)]">
                Link a named customer (with mobile) for credit, returns, and frequent-buyer analytics. Walk-in is fine
                for one-off cash/UPI.
              </p>
            )}
            {addingCustomer ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <input
                  className={fieldClass}
                  placeholder="Customer name"
                  value={newCustomerName}
                  onChange={(e) => setNewCustomerName(e.target.value)}
                />
                <input
                  className={fieldClass}
                  placeholder="Mobile number"
                  value={newCustomerPhone}
                  onChange={(e) => setNewCustomerPhone(e.target.value)}
                  inputMode="tel"
                />
                <select
                  className={fieldClass}
                  value={newCustomerType}
                  onChange={(e) => setNewCustomerType(e.target.value)}
                >
                  <option value="">Type: General</option>
                  {customerTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
                <button type="button" className="bg-[var(--accent)] text-[var(--on-accent)]" onClick={createCustomer}>
                  Save & select
                </button>
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[var(--shadow)]">
            <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Add items</p>
            <input
              className={`${fieldClass} mt-2`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, SKU, barcode, alias…"
              autoFocus
            />
            {hits.length ? (
              <ul className="mt-2 max-h-52 overflow-y-auto rounded-md border border-[var(--line)]">
                {hits.map((hit) => (
                  <li key={hit.id}>
                    <button
                      type="button"
                      className="flex w-full justify-between gap-3 rounded-none border-0 border-b border-[var(--line)] px-3 py-2 text-left shadow-none last:border-b-0"
                      onClick={() => addLine(hit)}
                    >
                      <span>
                        <span className="font-medium">{hit.name}</span>
                        <span className="mt-0.5 block text-xs text-[var(--muted)]">
                          {hit.sku}
                          {hit.specification ? ` · ${hit.specification}` : ""}
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-xs text-[var(--muted)]">
                        Next ₹{formatMoney(hit.active_selling_price)}
                        {hit.latest_selling_price &&
                        formatMoney(hit.latest_selling_price) !== formatMoney(hit.active_selling_price) ? (
                          <span className="mt-0.5 block">Newest ₹{formatMoney(hit.latest_selling_price)}</span>
                        ) : null}
                        <span className="mt-0.5 block">stock {formatMoney(hit.current_stock)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="mt-4 space-y-3">
              {lines.length === 0 ? (
                <p className="py-4 font-sans text-sm text-[var(--muted)]">
                  No items yet — search above and click a product to add it. Lower the bill price for a discount.
                </p>
              ) : (
                lines.map((line, index) => {
                  const qty = Number(line.quantity) || 0;
                  const list = Number(line.list_price) || 0;
                  const bill = Number(line.bill_price) || 0;
                  const lineTotal = qty * bill;
                  const deltaPct = listDeltaPercent(list, bill);
                  const discPct = Math.max(0, deltaPct);
                  const belowSafe = bill < Number(line.safe_selling_price);
                  const overMax =
                    Number(line.max_discount_percent) > 0 && discPct > Number(line.max_discount_percent);
                  const rangeOpen = Boolean(priceDetailOpen[line.product_id]);
                  const discLabel =
                    deltaPct === 0
                      ? "—"
                      : deltaPct > 0
                        ? `+${formatMoney(deltaPct)}%`
                        : `−${formatMoney(Math.abs(deltaPct))}%`;
                  const discClass =
                    deltaPct > 0
                      ? "font-bold text-[var(--danger)]"
                      : deltaPct < 0
                        ? "font-bold text-[var(--profit)]"
                        : "money money-discount-zero";
                  return (
                    <div
                      key={`${line.product_id}-${index}`}
                      className="rounded-lg border border-[var(--line)] bg-[var(--paper)] p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium">{line.name}</div>
                          {line.specification ? (
                            <p className="mt-0.5 font-sans text-sm text-[var(--ink)]">{line.specification}</p>
                          ) : null}
                          <div className="mt-1 flex flex-wrap items-center gap-2 font-sans text-[11px] text-[var(--muted)]">
                            <span>
                              {line.sku} · stock {line.stock}
                              {line.next_lot_code ? ` · next ${line.next_lot_code}` : ""}
                              {overMax ? " · over max discount" : ""}
                            </span>
                            <button
                              type="button"
                              className="h-7 rounded border border-[var(--line)] px-2 text-[11px] shadow-none"
                              onClick={() =>
                                setPriceDetailOpen((current) => ({
                                  ...current,
                                  [line.product_id]: !current[line.product_id],
                                }))
                              }
                              aria-expanded={rangeOpen}
                            >
                              {rangeOpen ? "Hide prices" : "Prices"}
                            </button>
                          </div>
                          {line.price_note ? (
                            <p className="mt-1 font-sans text-[11px] text-[var(--muted)]">{line.price_note}</p>
                          ) : null}
                          {rangeOpen ? (
                            <div className="mt-2 rounded-md border border-[var(--line)] bg-[var(--panel)] px-2.5 py-2 font-sans text-[11px] leading-relaxed text-[var(--muted)]">
                              {Number(line.mrp) > 0 ? `MRP ₹${line.mrp} · ` : ""}
                              Safe ₹{line.safe_selling_price} · List ₹{line.list_price}
                              {Number(line.max_discount_percent) > 0
                                ? ` · Max disc ${line.max_discount_percent}%`
                                : ""}
                            </div>
                          ) : null}
                        </div>
                        <button type="button" aria-label={`Remove ${line.name}`} onClick={() => removeLine(index)}>
                          Remove
                        </button>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-8">
                        {line.lots.length > 0 ? (
                          <label className="block font-sans text-sm sm:col-span-2 lg:col-span-2">
                            <span className="text-xs text-[var(--muted)]">Lot</span>
                            <select
                              className="mt-1 h-9 w-full rounded-md border border-[var(--accent)] bg-[var(--panel)] px-2 font-medium"
                              value={line.batch_id ?? line.lots[0]?.id ?? ""}
                              onChange={(e) => selectLot(index, Number(e.target.value))}
                            >
                              {line.lots.map((lot) => (
                                <option key={lot.id} value={lot.id}>
                                  {lot.lot_code}
                                  {lot.vendor_name ? ` · ${lot.vendor_name}` : ""} · ₹
                                  {formatMoney(lot.selling_price)} · {formatMoney(lot.remaining_quantity)} left
                                </option>
                              ))}
                            </select>
                          </label>
                        ) : (
                          <p className="sm:col-span-2 font-sans text-xs text-[var(--muted)]">No open lots loaded.</p>
                        )}
                        <label className="block font-sans text-sm">
                          <span className="text-xs text-[var(--muted)]">Qty</span>
                          <input
                            className="mt-1 h-9 w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-2"
                            value={line.quantity}
                            onChange={(e) =>
                              updateLine(index, { quantity: sanitizeDecimalInput(e.target.value, 2) })
                            }
                          />
                        </label>
                        <div className="block font-sans text-sm">
                          <span className="text-xs text-[var(--muted)]">List</span>
                          <p className="mt-1 flex h-9 items-center text-[var(--muted)]">₹{line.list_price}</p>
                        </div>
                        <div className="block font-sans text-sm">
                          <span className="text-xs text-[var(--muted)]">MRP</span>
                          <p className="money money-subtotal mt-1 flex h-9 items-center">
                            {Number(line.mrp) > 0 ? `₹${line.mrp}` : "—"}
                          </p>
                        </div>
                        <label className="block font-sans text-sm">
                          <span className="text-xs text-[var(--muted)]">Bill price</span>
                          <input
                            className={[
                              "mt-1 h-9 w-full rounded-md border bg-[var(--panel)] px-2 font-medium",
                              belowSafe
                                ? "border-[var(--danger)] text-[var(--danger)]"
                                : "border-[var(--line)]",
                            ].join(" ")}
                            value={line.bill_price}
                            onChange={(e) =>
                              updateLine(index, { bill_price: sanitizeDecimalInput(e.target.value, 2) })
                            }
                            title={
                              belowSafe
                                ? `Below safe ₹${line.safe_selling_price} — little or no profit`
                                : "Price charged to the customer"
                            }
                            aria-invalid={belowSafe}
                          />
                          {belowSafe ? (
                            <span className="mt-1 block text-[11px] text-[var(--danger)]">
                              Below safe ₹{line.safe_selling_price} — selling with little/no profit
                            </span>
                          ) : null}
                        </label>
                        <div className="block font-sans text-sm">
                          <span className="text-xs text-[var(--muted)]">Disc %</span>
                          <p className={["mt-1 flex h-9 items-center font-medium", discClass].join(" ")}>
                            {discLabel}
                          </p>
                        </div>
                        <div className="block font-sans text-sm">
                          <span className="text-xs text-[var(--muted)]">Line total</span>
                          <p className="money money-line mt-1 flex h-9 items-center">₹{formatMoney(lineTotal)}</p>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <aside className="h-fit rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[var(--shadow)] lg:sticky lg:top-4">
          <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Payment</p>
          <label className="mt-3 block font-sans text-sm">
            <span className="text-xs text-[var(--muted)]">Method</span>
            <select
              className={`${fieldClass} mt-1`}
              value={method}
              onChange={(e) => {
                setMethod(e.target.value);
                setPaidTouched(false);
                setTendered("");
                setPaymentReference("");
              }}
            >
              {["CASH", "UPI", "CARD", "BANK", "CREDIT"].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          {method === "CASH" ? (
            <>
              <label className="mt-3 block font-sans text-sm">
                <span className="text-xs text-[var(--muted)]">Cash given (₹)</span>
                <input
                  className={`${fieldClass} mt-1`}
                  value={tendered}
                  onChange={(e) => {
                    setTendered(sanitizeDecimalInput(e.target.value, 2));
                    setPaidTouched(false);
                  }}
                  placeholder="e.g. 200"
                />
              </label>
              <dl className="mt-2 space-y-1 font-sans text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Bill</dt>
                  <dd className="money money-total">₹{formatMoney(grandTotal)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Return change</dt>
                  <dd className="money money-change">₹{formatMoney(changeDue)}</dd>
                </div>
                {cashShort ? (
                  <p className="text-[11px] text-[var(--danger)]">
                    Cash is short by{" "}
                    <span className="money money-due">₹{formatMoney(grandTotal - cashGiven)}</span> — will post as
                    partial pay.
                  </p>
                ) : null}
              </dl>
            </>
          ) : null}
          {method === "UPI" || method === "CARD" || method === "BANK" ? (
            <>
              <label className="mt-3 block font-sans text-sm">
                <span className="text-xs text-[var(--muted)]">
                  {method} transaction ID <span className="text-[var(--muted)]">(optional)</span>
                </span>
                <input
                  className={`${fieldClass} mt-1`}
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                  placeholder="Paste UTR / txn id or leave blank"
                />
              </label>
              <label className="mt-3 block font-sans text-sm">
                <span className="text-xs text-[var(--muted)]">Amount paid (₹)</span>
                <input
                  className={`${fieldClass} mt-1`}
                  value={paid}
                  onChange={(e) => {
                    setPaidTouched(true);
                    setPaid(sanitizeDecimalInput(e.target.value, 2));
                  }}
                />
              </label>
              <button
                type="button"
                className="mt-2 w-full"
                onClick={() => {
                  setPaidTouched(true);
                  setPaid(formatMoney(grandTotal));
                }}
              >
                Mark fully paid with {method}
              </button>
            </>
          ) : null}
          {method === "CREDIT" ? (
            <p className="mt-3 font-sans text-xs text-[var(--muted)]">
              Credit sale — nothing collected now; balance goes to the customer ledger.
            </p>
          ) : null}
          <dl className="mt-4 space-y-2 border-t border-[var(--line)] pt-4 font-sans text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--muted)]">Items</dt>
              <dd className="money money-subtotal">{lines.length}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--muted)]">{referenceSubtotalLabel}</dt>
              <dd className="money money-subtotal">₹{formatMoney(referenceSubtotal)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className={referenceDiscount > 0 ? "font-semibold text-[var(--discount)]" : "text-[var(--muted)]"}>
                Discount
              </dt>
              <dd className={referenceDiscount > 0 ? "money money-discount" : "money money-discount-zero"}>
                −₹{formatMoney(referenceDiscount)}
              </dd>
            </div>
            <div className="money-bill-row flex justify-between gap-3">
              <dt className="font-bold">Bill total</dt>
              <dd className="money money-total">₹{formatMoney(grandTotal)}</dd>
            </div>
            {method !== "CASH" ? (
              <div className="flex justify-between gap-3">
                <dt className={amountDue > 0 ? "font-semibold text-[var(--danger)]" : "text-[var(--muted)]"}>
                  Still due
                </dt>
                <dd className={amountDue > 0 ? "money money-due" : "money money-due-clear"}>
                  ₹{formatMoney(amountDue)}
                </dd>
              </div>
            ) : null}
          </dl>
          {warning ? (
            <p className="mt-3 rounded-md border border-[var(--warn-line)] bg-[var(--warn-bg)] px-3 py-2 text-sm text-[var(--warn-ink)]">
              {warning}
            </p>
          ) : null}
          {warning.toLowerCase().includes("safe") ? (
            <button type="button" className="mt-3 w-full" onClick={() => post(true)} disabled={busy}>
              Override safe price & {editingSaleId ? "update" : "complete"}
            </button>
          ) : null}
          <button
            type="button"
            className="mt-3 w-full bg-[var(--accent)] text-[var(--on-accent)]"
            disabled={busy || !lines.length}
            onClick={() => post(false)}
          >
            {busy ? "Posting…" : editingSaleId ? "Update sale" : "Complete sale"}
          </button>
          <p className="mt-3 text-xs text-[var(--muted)]">
            Cash: enter notes given and return the change shown. UPI: optional txn id, or just mark paid.
          </p>
        </aside>
      </div>

      {invoice ? (
        <article className="mt-8 rounded-xl border border-[var(--line)] bg-[var(--panel)] p-6 shadow-[var(--shadow)]">
          <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Customer invoice</p>
          <h3 className="mt-1 text-2xl">Invoice {String(invoice.invoice_number)}</h3>
          <p className="mt-1 font-sans text-sm text-[var(--muted)]">
            {String(invoice.customer || "Walk-in")} · {String(invoice.invoice_date)}
          </p>
          {invoiceItems.length ? (
            <table className="mt-4 w-full font-sans text-sm">
              <thead>
                <tr className="text-left text-[var(--muted)]">
                  <th className="py-1 pr-2">Item</th>
                  <th className="py-1 pr-2">Qty</th>
                  <th className="py-1 pr-2">Rate</th>
                  {invoiceHasMrp ? <th className="py-1 pr-2">MRP</th> : null}
                  {invoiceHasDiscount ? <th className="py-1 pr-2">Disc</th> : null}
                  <th className="py-1">Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoiceItems.map((item, index) => (
                  <tr key={index} className="border-t border-[var(--line)]">
                    <td className="py-2 pr-2">
                      <div>{item.name}</div>
                      {item.specification ? (
                        <div className="text-xs text-[var(--muted)]">{item.specification}</div>
                      ) : null}
                    </td>
                    <td className="py-2 pr-2">{formatMoney(item.quantity)}</td>
                    <td className="py-2 pr-2">₹{formatMoney(item.unit_price)}</td>
                    {invoiceHasMrp ? (
                      <td className="money money-subtotal py-2 pr-2">
                        {Number(item.mrp ?? 0) > 0 ? `₹${formatMoney(item.mrp)}` : "—"}
                      </td>
                    ) : null}
                    {invoiceHasDiscount ? (
                      <td className="py-2 pr-2">
                        {Number(item.discount ?? 0) > 0 ? (
                          <span className="money money-discount">₹{formatMoney(item.discount)}</span>
                        ) : (
                          <span className="money money-discount-zero">—</span>
                        )}
                      </td>
                    ) : null}
                    <td className="money money-line py-2">₹{formatMoney(item.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <dl className="mt-4 space-y-2 font-sans text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Subtotal</dt>
              <dd className="money money-subtotal">₹{formatMoney(String(invoice.subtotal))}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt
                className={
                  Number(invoice.discount_amount ?? 0) > 0
                    ? "font-semibold text-[var(--discount)]"
                    : "text-[var(--muted)]"
                }
              >
                Discount
              </dt>
              <dd
                className={
                  Number(invoice.discount_amount ?? 0) > 0 ? "money money-discount" : "money money-discount-zero"
                }
              >
                −₹{formatMoney(String(invoice.discount_amount ?? "0"))}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">GST</dt>
              <dd className="money money-subtotal">₹{formatMoney(String(invoice.gst_amount))}</dd>
            </div>
            <div className="money-bill-row flex justify-between gap-4">
              <dt className="font-bold">Grand total</dt>
              <dd className="money money-total">₹{formatMoney(String(invoice.grand_total))}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Paid</dt>
              <dd className="money money-paid">
                ₹{formatMoney(String(invoice.amount_paid))}
                <span className="ml-1 font-sans text-xs font-normal text-[var(--muted)]">
                  ({String(invoice.payment_method || "")})
                </span>
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className={Number(invoice.amount_due) > 0 ? "font-semibold text-[var(--danger)]" : "text-[var(--muted)]"}>
                Due
              </dt>
              <dd className={Number(invoice.amount_due) > 0 ? "money money-due" : "money money-due-clear"}>
                ₹{formatMoney(String(invoice.amount_due))}
              </dd>
            </div>
            {Number(invoice.amount_tendered ?? 0) > 0 && String(invoice.payment_method) === "CASH" ? (
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Cash given · Change</dt>
                <dd>
                  <span className="money money-subtotal">₹{formatMoney(String(invoice.amount_tendered))}</span>
                  <span className="text-[var(--muted)]"> · </span>
                  <span className="money money-change">₹{formatMoney(String(invoice.change_given))}</span>
                </dd>
              </div>
            ) : null}
            {invoice.payment_reference ? (
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Txn / ref</dt>
                <dd>{String(invoice.payment_reference)}</dd>
              </div>
            ) : null}
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="bg-[var(--accent)] text-[var(--on-accent)]" onClick={printInvoice}>
              Print A4
            </button>
            <button type="button" onClick={editLastBill} disabled={busy}>
              Edit bill
            </button>
            <button type="button" onClick={newBill}>
              Start next bill
            </button>
          </div>
        </article>
      ) : null}
    </section>
  );
};
