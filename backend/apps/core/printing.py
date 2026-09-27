"""Printer-neutral invoice HTML. Business totals stay in services; this only renders."""

from __future__ import annotations


class InvoicePrintService:
    """
    Customer-facing A4 / thermal layouts.

    Shop-only fields (cost, safe price, lot codes, margins, cash tender / change)
    are never printed. MRP prints when set on the lot. Discount appears only when
    the customer saved money.
    """

    def render(self, payload: dict, *, kind: str = "a4") -> str:
        shop = payload.get("shop_name") or "Shop"
        address = payload.get("shop_address") or ""
        gstin = payload.get("shop_gstin") or ""
        phone = payload.get("shop_phone") or ""
        number = payload.get("invoice_number") or ""
        date = payload.get("invoice_date") or ""
        customer = payload.get("customer") or "Walk-in"
        items = payload.get("items") or []
        discount_total = payload.get("discount_amount") or "0"
        # Customer "profit" = paid below list; hide the discount column/total otherwise.
        show_discount = float(discount_total or 0) > 0
        show_mrp = any(float(item.get("mrp") or 0) > 0 for item in items)
        method = payload.get("payment_method") or ""
        pay_ref = payload.get("payment_reference") or ""

        def _row(item: dict) -> str:
            name = item.get("name") or ""
            spec = (item.get("specification") or "").strip()
            label = f"{name}<br/><span class='muted'>{spec}</span>" if spec else name
            qty = item.get("quantity") or ""
            rate = item.get("unit_price") or ""
            mrp = item.get("mrp") or "0"
            disc = item.get("discount") or "0"
            total = item.get("line_total") or ""
            mrp_cell = f"<td>{mrp if float(mrp or 0) > 0 else '—'}</td>" if show_mrp else ""
            # Only show a disc cell when this invoice has any customer savings.
            disc_cell = f"<td>{disc}</td>" if show_discount else ""
            return (
                f"<tr><td>{label}</td><td>{qty}</td><td>{rate}</td>{mrp_cell}{disc_cell}<td>{total}</td></tr>"
            )

        rows = "".join(map(_row, items))
        head_mrp = "<th>MRP</th>" if show_mrp else ""
        head_disc = "<th>Disc</th>" if show_discount else ""
        width = "80mm" if kind == "thermal" else "210mm"
        font = "12px" if kind == "thermal" else "14px"
        address_html = f"<p>{address}</p>" if address else ""
        meta_bits = " · ".join(filter(None, [f"GSTIN {gstin}" if gstin else "", f"Ph {phone}" if phone else ""]))
        meta_html = f"<p>{meta_bits}</p>" if meta_bits else ""
        disc_line = (
            f'<p class="discount">You saved ₹{discount_total}</p>' if show_discount else ""
        )
        ref_line = f"<p>{method} ref: {pay_ref}</p>" if pay_ref else ""
        return f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>{number}</title>
<style>
  @page {{ size: {width} auto; margin: 10mm; }}
  body {{ font-family: "Segoe UI", sans-serif; font-size: {font}; color: #111; }}
  h1 {{ margin: 0 0 4px; font-size: 1.4em; }}
  .muted {{ color: #555; font-size: 0.9em; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 6px 4px; text-align: left; vertical-align: top; }}
  th {{ font-size: 0.85em; color: #444; }}
  .totals {{ margin-top: 14px; }}
  .totals p {{ margin: 4px 0; }}
  .totals .discount {{ font-weight: 700; color: #1f7a4d; }}
  .thanks {{ margin-top: 18px; color: #555; font-size: 0.9em; }}
</style></head>
<body>
  <h1>{shop}</h1>
  {address_html}
  {meta_html}
  <p><strong>Invoice</strong> {number}<br/><span class="muted">{date}</span></p>
  <p>Bill to: {customer}</p>
  <table>
    <thead><tr><th>Item</th><th>Qty</th><th>Rate</th>{head_mrp}{head_disc}<th>Amount</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="totals">
    <p>Subtotal ₹{payload.get("subtotal", "")}</p>
    {disc_line}
    <p>GST ₹{payload.get("gst_amount", "")}</p>
    <p><strong>Grand total ₹{payload.get("grand_total", "")}</strong></p>
    <p>Paid ₹{payload.get("amount_paid", "")} ({method}) · Balance ₹{payload.get("amount_due", "")}</p>
    {ref_line}
  </div>
  <p class="thanks">Thank you for your purchase.</p>
  <script>window.onload = function () {{ window.print(); }};</script>
</body></html>"""


invoice_print_service = InvoicePrintService()
