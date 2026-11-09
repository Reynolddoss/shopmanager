"""
GST retail invoice HTML.

Totals stay in InvoicePayloadService. This module only draws the bill: a boxed
tax invoice like a retailer GST format (supplier, receiver, HSN lines, tax
summary, signature). GST on this shop is added on top of the selling price,
so the rate column is the taxable rate, not an MRP-inclusive price.
"""

from __future__ import annotations

import html
import re
from decimal import Decimal, InvalidOperation

from apps.core.models import InvoiceCopy


class HtmlText:
    """Escape shop-entered text before it is placed in the bill HTML."""

    @staticmethod
    def escape(value: object) -> str:
        """Return text that cannot break the invoice markup."""
        return html.escape("" if value is None else str(value), quote=True)

    @staticmethod
    def paragraphs(value: object) -> str:
        """Keep an address or terms block, one escaped line per row."""
        lines = list(
            filter(
                None,
                map(lambda line: HtmlText.escape(line.strip()), str(value or "").splitlines()),
            )
        )
        return "<br/>".join(lines)

    @staticmethod
    def parts(value: object) -> list[str]:
        """Split GSTINs, phones, or emails typed on separate lines or with commas."""
        chunks = re.split(r"[\n,;]+", str(value or ""))
        return list(filter(None, map(lambda chunk: chunk.strip(), chunks)))


class MoneyText:
    """Print rupee amounts with two decimal places."""

    @staticmethod
    def amount(value: object) -> str:
        """Format a number. Non-numeric text is escaped and returned as-is."""
        try:
            quant = Decimal(str(value if value not in (None, "") else "0")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return HtmlText.escape(value)
        return f"{quant:.2f}"

    @staticmethod
    def percent(value: object) -> str:
        """Print a GST rate as 18 or 2.5, without trailing zeros."""
        quant = MoneyText.decimal(value).quantize(Decimal("0.01"))
        text = f"{quant:.2f}".rstrip("0").rstrip(".")
        return text or "0"

    @staticmethod
    def decimal(value: object) -> Decimal:
        """Parse a payload number. Bad values become zero."""
        try:
            return Decimal(str(value if value not in (None, "") else "0"))
        except (InvalidOperation, ValueError):
            return Decimal("0")


class RupeesInWords:
    """Spell an invoice total in Indian numbering (lakh, crore)."""

    BELOW_TWENTY = (
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    )
    TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")

    def format(self, value: object) -> str:
        """Return 'One Hundred Eighteen Rupees Only' for 118.00."""
        quant = MoneyText.decimal(value).quantize(Decimal("0.01"))
        rupees = int(quant)
        paise = int((quant - Decimal(rupees)) * 100)
        words = self._indian(rupees) or "Zero"
        text = f"{words} Rupees"
        if paise:
            text += f" and {self._indian(paise)} Paise"
        return f"{text} Only"

    def _indian(self, number: int) -> str:
        """Group an integer as crore, lakh, thousand, then hundreds."""
        if number <= 0:
            return ""
        crore, number = divmod(number, 10_000_000)
        lakh, number = divmod(number, 100_000)
        thousand, number = divmod(number, 1_000)
        chunks = [
            f"{self._below_thousand(crore)} Crore" if crore else "",
            f"{self._below_thousand(lakh)} Lakh" if lakh else "",
            f"{self._below_thousand(thousand)} Thousand" if thousand else "",
            self._below_thousand(number),
        ]
        return " ".join(filter(None, chunks))

    def _below_thousand(self, number: int) -> str:
        """Spell 0–999."""
        hundred, rest = divmod(number, 100)
        head = f"{self.BELOW_TWENTY[hundred]} Hundred" if hundred else ""
        if rest < 20:
            tail = self.BELOW_TWENTY[rest]
        else:
            ten, one = divmod(rest, 10)
            tail = " ".join(filter(None, (self.TENS[ten], self.BELOW_TWENTY[one])))
        return " ".join(filter(None, (head, tail)))


class GstStateCodes:
    """First two digits of a GSTIN are the state code (place of supply)."""

    NAMES = {
        "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
        "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
        "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
        "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
        "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
        "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
        "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
        "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
        "38": "Ladakh", "97": "Other Territory",
    }

    def code(self, gstin: object) -> str:
        """Return the state code from the first GSTIN, or an empty string."""
        first = next(iter(HtmlText.parts(gstin)), "")
        digits = first[:2]
        return digits if digits.isdigit() else ""

    def name(self, gstin: object) -> str:
        """Return the state name for a GSTIN."""
        return self.NAMES.get(self.code(gstin), "")


class GstTaxSplit:
    """
    Show CGST and SGST, or a single IGST.

    Same state, or a walk-in customer with no GSTIN: split the stored GST in half.
    Different state codes: the whole GST amount is IGST. The stored total does not change.
    """

    def __init__(self) -> None:
        self.states = GstStateCodes()

    def interstate(self, payload: dict) -> bool:
        """True only when both GSTINs name a state and those states differ."""
        shop = self.states.code(payload.get("shop_gstin"))
        customer = self.states.code(payload.get("customer_gstin"))
        return bool(shop and customer and shop != customer)

    def halves(self, amount: object) -> tuple[Decimal, Decimal]:
        """Split one GST figure into two paise-safe halves."""
        total = MoneyText.decimal(amount).quantize(Decimal("0.01"))
        first = (total / 2).quantize(Decimal("0.01"))
        return first, (total - first).quantize(Decimal("0.01"))


class InvoiceLogo:
    """MM Electricals mark, used until the shop uploads its own logo."""

    @staticmethod
    def markup(*, size: int) -> str:
        """Return an SVG logo at the requested pixel size."""
        return (
            f'<svg class="logo" width="{size}" height="{size}" viewBox="0 0 64 64" aria-hidden="true">'
            '<rect x="2" y="2" width="60" height="60" rx="14" fill="#c2410c"/>'
            '<polygon fill="#fff" points="38,8 18,34 31,34 26,56 48,26 34,26 40,8"/>'
            "</svg>"
        )


class InvoicePrintService:
    """
    Customer-facing A4 and thermal GST invoices.

    Cost, safe price, lot codes, margins, cash tender, and change are never printed.
    """

    SHOP_FALLBACK = "MM Electricals"

    def __init__(self) -> None:
        self.words = RupeesInWords()
        self.states = GstStateCodes()
        self.tax = GstTaxSplit()

    def render(self, payload: dict, *, kind: str = "a4") -> str:
        """Build a complete HTML document and ask the browser to print it."""
        thermal = kind == "thermal"
        items = payload.get("items") or []
        show_discount = MoneyText.decimal(payload.get("discount_amount")) > 0
        show_mrp = any(MoneyText.decimal(item.get("mrp")) > 0 for item in items)
        shop = HtmlText.escape(payload.get("shop_name") or self.SHOP_FALLBACK)
        return f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>{HtmlText.escape(payload.get("invoice_number") or "Tax Invoice")}</title>
<style>{self._styles(thermal=thermal)}</style></head>
<body class="{'thermal' if thermal else 'a4'}">
  <div class="sheet">
    {self._header(payload, shop, thermal=thermal)}
    {self._parties(payload)}
    {self._table(items, show_mrp=show_mrp, show_discount=show_discount, interstate=self.tax.interstate(payload))}
    {self._summary(payload, show_discount=show_discount)}
    {self._footer(payload, shop)}
  </div>
  <script>
    /* Pin the sheet to a physical A4 page, then grow the ruled grid into the spare space. */
    window.onload = () => {{
      const sheet = document.querySelector(".sheet");
      const wrap = document.querySelector(".grid-wrap");
      const table = document.querySelector(".grid");
      if (sheet && wrap && table && !document.body.classList.contains("thermal")) {{
        const probe = document.createElement("div");
        probe.style.cssText = "position:absolute;width:210mm;height:297mm;visibility:hidden";
        document.body.appendChild(probe);
        sheet.style.width = probe.offsetWidth + "px";
        sheet.style.minHeight = probe.offsetHeight + "px";
        probe.remove();
        table.style.height = wrap.clientHeight + "px";
      }}
      window.print();
    }};
  </script>
</body></html>"""

    def _header(self, payload: dict, shop: str, *, thermal: bool) -> str:
        """Supplier block on the left, TAX INVOICE and invoice number on the right."""
        logo = self._logo_markup(payload, thermal=thermal)
        address = HtmlText.paragraphs(payload.get("shop_address"))
        address_html = f"<p>{address}</p>" if address else ""
        phones = HtmlText.parts(payload.get("shop_phone")) + HtmlText.parts(payload.get("shop_alternate_phone"))
        emails = HtmlText.parts(payload.get("shop_email"))
        gstins = HtmlText.parts(payload.get("shop_gstin"))
        method = "Credit" if str(payload.get("payment_method") or "").upper() == "CREDIT" else "Cash"
        return f"""<table class="box header-table">
  <tr>
    <td class="supplier">
      <div class="brand-row">{logo}<div>
        <p class="kicker">Supplier</p>
        <h1>{shop}</h1>
        {address_html}
        {self._labeled("Phone", phones)}
        {self._labeled("Email", emails)}
        {self._labeled("GSTIN", gstins)}
      </div></div>
    </td>
    <td class="inv-meta">
      <p class="doc-title">TAX INVOICE</p>
      <p><span class="kicker">Invoice no.</span><br/><strong>{HtmlText.escape(payload.get("invoice_number") or "")}</strong></p>
      <p><span class="kicker">Invoice date</span><br/>{HtmlText.escape(payload.get("invoice_date") or "")}</p>
      <p><span class="kicker">Mode</span><br/>{method}</p>
    </td>
  </tr>
</table>"""

    def _parties(self, payload: dict) -> str:
        """Receiver on the left, place of supply on the right."""
        customer = HtmlText.escape(payload.get("customer") or "Walk-in")
        address = HtmlText.paragraphs(payload.get("customer_address"))
        address_html = f"<p>{address}</p>" if address else ""
        phones = HtmlText.parts(payload.get("customer_phone")) + HtmlText.parts(payload.get("customer_alternate_phone"))
        place = self.states.name(payload.get("customer_gstin")) or self.states.name(payload.get("shop_gstin")) or "—"
        kind = "IGST (inter-state)" if self.tax.interstate(payload) else "CGST + SGST (intra-state)"
        return f"""<table class="box party-table">
  <tr>
    <td>
      <p class="kicker">Details of receiver (billed to)</p>
      <p class="customer">{customer}</p>
      {address_html}
      {self._labeled("Phone", phones)}
      {self._labeled("GSTIN", HtmlText.parts(payload.get("customer_gstin")))}
    </td>
    <td class="inv-meta">
      <p class="kicker">Place of supply</p>
      <p><strong>{HtmlText.escape(place)}</strong></p>
      <p class="muted">{kind}</p>
    </td>
  </tr>
</table>"""

    def _table(self, items: list, *, show_mrp: bool, show_discount: bool, interstate: bool) -> str:
        """Item grid: description, HSN, qty, taxable value, and the tax column for this supply."""
        head_mrp = "<th class='num'>MRP</th>" if show_mrp else ""
        head_disc = "<th class='num'>Disc</th>" if show_discount else ""
        tax_heads = "<th class='num'>IGST</th>" if interstate else "<th class='num'>CGST</th><th class='num'>SGST</th>"

        def _row(pair: tuple[int, dict]) -> str:
            index, item = pair
            name = HtmlText.escape(item.get("name") or "")
            spec = HtmlText.escape((item.get("specification") or "").strip())
            label = f"{name}<br/><span class='muted'>{spec}</span>" if spec else name
            taxable = self._line_taxable(item)
            gst = MoneyText.decimal(item.get("gst_amount")).quantize(Decimal("0.01"))
            amount = taxable + gst if item.get("gst_amount") not in (None, "") else MoneyText.decimal(item.get("line_total") or taxable)
            mrp_cell = ""
            if show_mrp:
                mrp = MoneyText.decimal(item.get("mrp"))
                mrp_cell = f"<td class='num'>{MoneyText.amount(mrp) if mrp > 0 else '—'}</td>"
            disc_cell = f"<td class='num'>{MoneyText.amount(item.get('discount'))}</td>" if show_discount else ""
            if interstate:
                tax_cells = f"<td class='num'>{MoneyText.amount(gst)}</td>"
            else:
                cgst, sgst = self.tax.halves(gst)
                tax_cells = f"<td class='num'>{MoneyText.amount(cgst)}</td><td class='num'>{MoneyText.amount(sgst)}</td>"
            return (
                "<tr>"
                f"<td class='num'>{index}</td>"
                f"<td>{label}</td>"
                f"<td>{HtmlText.escape(item.get('hsn') or '—')}</td>"
                f"<td class='num'>{HtmlText.escape(item.get('quantity') or '')}</td>"
                f"<td class='num'>{MoneyText.amount(item.get('unit_price'))}</td>"
                f"{mrp_cell}{disc_cell}"
                f"<td class='num'>{MoneyText.amount(taxable)}</td>"
                f"<td class='num'>{MoneyText.percent(item.get('gst_rate'))}%</td>"
                f"{tax_cells}"
                f"<td class='num'>{MoneyText.amount(amount)}</td>"
                "</tr>"
            )

        rows = "".join(map(_row, enumerate(items, start=1)))
        columns = self._column_count(show_mrp=show_mrp, show_discount=show_discount, interstate=interstate)
        # One empty row grows so the ruled columns reach the totals on a short bill.
        filler = "<tr class=\"filler\">" + "".join(map(lambda _: "<td></td>", range(columns))) + "</tr>"
        body = rows or "<tr><td colspan='%s'>—</td></tr>" % columns
        return f"""<div class="grid-wrap"><table class="grid">
  <thead>
    <tr>
      <th class="num">#</th><th>Description</th><th>HSN</th><th class="num">Qty</th><th class="num">Rate</th>
      {head_mrp}{head_disc}<th class="num">Taxable</th><th class="num">GST %</th>{tax_heads}<th class="num">Amount</th>
    </tr>
  </thead>
  <tbody>{body}{filler}</tbody>
</table></div>"""

    def _summary(self, payload: dict, *, show_discount: bool) -> str:
        """Taxable total, CGST/SGST or IGST, grand total, and the amount in words."""
        taxable = MoneyText.decimal(payload.get("subtotal")) - MoneyText.decimal(payload.get("discount_amount"))
        gst = MoneyText.decimal(payload.get("gst_amount"))
        discount_row = ""
        if show_discount:
            discount_row = f"<tr><td>Discount</td><td class='num'>{MoneyText.amount(payload.get('discount_amount'))}</td></tr>"
        if self.tax.interstate(payload):
            tax_rows = f"<tr><td>IGST</td><td class='num'>{MoneyText.amount(gst)}</td></tr>"
        else:
            cgst, sgst = self.tax.halves(gst)
            tax_rows = (
                f"<tr><td>CGST</td><td class='num'>{MoneyText.amount(cgst)}</td></tr>"
                f"<tr><td>SGST</td><td class='num'>{MoneyText.amount(sgst)}</td></tr>"
            )
        method = HtmlText.escape(payload.get("payment_method") or "")
        reference = HtmlText.escape(payload.get("payment_reference") or "")
        ref_row = f"<tr><td colspan='2' class='muted'>{method} ref: {reference}</td></tr>" if reference else ""
        return f"""<table class="box summary">
  <tr>
    <td class="words">
      <p class="kicker">Amount in words</p>
      <p>{HtmlText.escape(self.words.format(payload.get("grand_total")))}</p>
    </td>
    <td>
      <table class="totals">
        <tr><td>Taxable value</td><td class="num">{MoneyText.amount(taxable)}</td></tr>
        {discount_row}
        {tax_rows}
        <tr class="grand"><td>Grand total</td><td class="num">{MoneyText.amount(payload.get("grand_total"))}</td></tr>
        <tr><td>Received</td><td class="num">{MoneyText.amount(payload.get("amount_paid"))} ({method})</td></tr>
        <tr><td>Balance</td><td class="num">{MoneyText.amount(payload.get("amount_due"))}</td></tr>
        {ref_row}
      </table>
    </td>
  </tr>
</table>"""

    def _footer(self, payload: dict, shop: str) -> str:
        """Terms on the left and the authorised signature on the right, at the foot of the page."""
        terms = HtmlText.paragraphs(payload.get("invoice_terms") or InvoiceCopy.DEFAULT_TERMS)
        if not terms:
            terms = HtmlText.paragraphs(InvoiceCopy.DEFAULT_TERMS)
        signatory = HtmlText.escape((payload.get("authorised_signatory") or "").strip())
        name_html = f'<p class="sign-name">{signatory}</p>' if signatory else ""
        return f"""<footer class="footer">
  <div class="terms">
    <p class="kicker">Terms and conditions</p>
    <p>{terms}</p>
  </div>
  <div class="sign">
    <p>For {shop}</p>
    <div class="sign-line"></div>
    {name_html}
    <p class="muted">Authorised signatory</p>
  </div>
</footer>"""

    def _logo_markup(self, payload: dict, *, thermal: bool) -> str:
        """Uploaded logo when the shop has one; otherwise the built-in bolt mark."""
        size = 36 if thermal else 58
        data = str(payload.get("shop_logo_data") or "")
        if data.startswith("data:image/"):
            return f'<img class="logo" src="{HtmlText.escape(data)}" width="{size}" height="{size}" alt=""/>'
        return InvoiceLogo.markup(size=size)

    def _labeled(self, label: str, values: list[str]) -> str:
        """One line per phone, email, or GSTIN."""
        escaped = list(map(HtmlText.escape, values))
        if not escaped:
            return ""
        body = "<br/>".join(map(lambda value: f"<strong>{label}</strong> {value}", escaped))
        return f"<p>{body}</p>"

    def _column_count(self, *, show_mrp: bool, show_discount: bool, interstate: bool) -> int:
        """How many cells a body row has, including the optional MRP, discount, and tax columns."""
        extras = (1 if show_mrp else 0) + (1 if show_discount else 0) + (1 if interstate else 2)
        return 8 + extras

    def _line_taxable(self, item: dict) -> Decimal:
        """Taxable value of one line. Prefer line total minus its GST when both were stored."""
        if item.get("gst_amount") not in (None, ""):
            return (MoneyText.decimal(item.get("line_total")) - MoneyText.decimal(item.get("gst_amount"))).quantize(Decimal("0.01"))
        gross = MoneyText.decimal(item.get("quantity")) * MoneyText.decimal(item.get("unit_price"))
        return (gross - MoneyText.decimal(item.get("discount"))).quantize(Decimal("0.01"))

    def _styles(self, *, thermal: bool) -> str:
        """Boxed A4 tax invoice. Thermal keeps the same sections on a narrow roll."""
        page = "80mm auto" if thermal else "210mm 297mm"
        font = "10px" if thermal else "11px"
        return f"""
  @page {{ size: {page}; margin: 0; }}
  * {{ box-sizing: border-box; }}
  :root {{ color-scheme: light; }}
  html, body {{ margin: 0; padding: 0; background: #fff; }}
  body {{ margin: 0; font-family: "Segoe UI", sans-serif; font-size: {font}; color: #111; background: #fff; }}
  body.a4, body.a4 .sheet {{ width: 210mm; }}
  body.a4 .sheet {{ min-height: 297mm; padding: 8mm; }}
  .sheet {{ display: flex; flex-direction: column; }}
  .grid-wrap {{ flex: 1 1 auto; display: flex; flex-direction: column; }}
  table.grid {{ height: 100%; }}
  tr.filler td {{ height: 100%; }}
  h1 {{ margin: 0 0 2px; font-size: 1.35em; }}
  p {{ margin: 1px 0; }}
  .muted {{ color: #333; }}
  .kicker {{ font-size: 0.72em; letter-spacing: 0.06em; text-transform: uppercase; color: #333; font-weight: 700; }}
  .doc-title {{ margin: 0 0 6px; font-size: 1.35em; font-weight: 800; letter-spacing: 0.12em; text-align: right; }}
  .customer {{ font-weight: 700; }}
  table.box, table.grid {{ width: 100%; border-collapse: collapse; }}
  table.box > tbody > tr > td, table.grid th, table.grid td {{ border: 1px solid #222; padding: 4px 5px; vertical-align: top; }}
  table.grid th {{ font-size: 0.72em; letter-spacing: 0.04em; text-transform: uppercase; background: #f3f3f3; text-align: left; }}
  table.header-table td.supplier {{ width: 62%; }}
  table.party-table td {{ width: 50%; }}
  .inv-meta {{ text-align: right; }}
  .brand-row {{ display: flex; gap: 8px; align-items: flex-start; }}
  .logo {{ flex: 0 0 auto; object-fit: contain; }}
  td.num, th.num {{ text-align: right; white-space: nowrap; }}
  table.summary td {{ width: 50%; }}
  table.totals {{ width: 100%; border-collapse: collapse; }}
  table.totals td {{ border: 0; border-bottom: 1px solid #ddd; padding: 3px 0; }}
  table.totals .grand td {{ font-weight: 800; font-size: 1.05em; border-top: 2px solid #111; }}
  .footer {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; padding-top: 8px; }}
  .terms {{ flex: 1; font-size: 0.85em; max-width: 68%; }}
  .sign {{ width: 52mm; text-align: center; }}
  .sign-line {{ height: 42px; border-bottom: 1px solid #111; margin: 6px 8px 3px; }}
  .sign-name {{ font-weight: 700; }}
  body.thermal .sheet {{ min-height: auto; }}
  body.thermal .grid-wrap {{ flex: none; }}
  body.thermal table.grid {{ height: auto; }}
  body.thermal tr.filler {{ display: none; }}
  body.thermal .footer, body.thermal .brand-row {{ display: block; }}
  body.thermal .sign {{ width: auto; margin-top: 8px; text-align: left; }}
  body.thermal .terms {{ max-width: none; }}
  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    table.grid th {{ background: #f3f3f3; }}
  }}
"""


invoice_print_service = InvoicePrintService()
