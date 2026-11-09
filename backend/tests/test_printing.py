"""Printed bill letterhead, customer GSTIN, and signature footer."""

from __future__ import annotations

from apps.core.printing import invoice_print_service


class TestInvoicePrintLayout:
    """The customer bill carries shop identity and a place to sign."""

    def payload(self) -> dict:
        """A small bill with two contact values and no customer discount."""
        return {
            "shop_name": "MM Electricals",
            "shop_address": "12 Market Road\nKochi",
            "shop_gstin": "32AAAAA0000A1Z5, 32BBBBB0000B1Z8",
            "shop_phone": "0484-000000",
            "shop_alternate_phone": "9000000000",
            "shop_email": "shop@mm.example, accounts@mm.example",
            "authorised_signatory": "R. Nair",
            "invoice_terms": "Goods once sold are final.",
            "invoice_number": "SH-1001",
            "invoice_date": "2026-10-20",
            "customer": "Walk-in <script>",
            "customer_gstin": "29ABCDE1234F1Z5",
            "customer_phone": "9111111111",
            "customer_address": "Near the temple",
            "items": [
                {
                    "name": "Switch",
                    "specification": "6A",
                    "hsn": "8536",
                    "gst_rate": "18",
                    "gst_amount": "18.00",
                    "quantity": "2",
                    "unit_price": "50.00",
                    "mrp": "60.00",
                    "discount": "0",
                    "line_total": "118.00",
                }
            ],
            "subtotal": "100.00",
            "discount_amount": "0",
            "gst_amount": "18.00",
            "grand_total": "118.00",
            "amount_paid": "118.00",
            "amount_due": "0.00",
            "payment_method": "CASH",
            "payment_reference": "",
        }

    def test_a4_shows_letterhead_logo_and_footer(self) -> None:
        html = invoice_print_service.render(self.payload(), kind="a4")
        assert "TAX INVOICE" in html
        assert 'class="filler"' in html
        assert "height: 100%" in html
        assert "wrap.clientHeight" in html
        assert "210mm" in html
        assert "297mm" in html
        assert "<svg" in html
        assert "MM Electricals" in html
        assert "12 Market Road" in html
        assert "32AAAAA0000A1Z5" in html
        assert "32BBBBB0000B1Z8" in html
        assert "0484-000000" in html
        assert "9000000000" in html
        assert "shop@mm.example" in html
        assert "accounts@mm.example" in html
        assert "29ABCDE1234F1Z5" in html
        assert "HSN" in html
        assert "8536" in html
        assert "IGST" in html
        assert "Karnataka" in html
        assert "R. Nair" in html
        assert "Authorised signatory" in html
        assert "Goods once sold are final." in html
        assert "You saved" not in html
        assert "<script>" not in html.split("Walk-in")[1][:40]
        assert "Walk-in &lt;script&gt;" in html

    def test_same_state_splits_gst_into_cgst_and_sgst(self) -> None:
        payload = self.payload()
        payload["customer_gstin"] = "32CCCCC0000C1Z5"
        html = invoice_print_service.render(payload, kind="a4")
        assert "CGST" in html
        assert "SGST" in html
        assert "intra-state" in html
        assert ">IGST<" not in html

    def test_uploaded_logo_replaces_the_built_in_mark(self) -> None:
        payload = self.payload()
        payload["shop_logo_data"] = "data:image/png;base64,aaaa"
        html = invoice_print_service.render(payload, kind="a4")
        assert 'src="data:image/png;base64,aaaa"' in html
        assert "<svg" not in html

    def test_blank_terms_use_the_longer_default(self) -> None:
        payload = self.payload()
        payload["invoice_terms"] = ""
        html = invoice_print_service.render(payload, kind="a4")
        assert "paid in full" in html
        assert "time of delivery" in html

    def test_thermal_uses_the_narrow_layout(self) -> None:
        html = invoice_print_service.render(self.payload(), kind="thermal")
        assert 'class="thermal"' in html
        assert "80mm" in html
