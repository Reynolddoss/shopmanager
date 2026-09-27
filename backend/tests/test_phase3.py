"""Phase 3 purchases, sales, ledgers, returns, and invoice numbering."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client
from rest_framework.exceptions import ValidationError

from apps.core.models import AuditLog, DocumentSequence
from apps.core.numbering import document_number_service
from apps.customers.models import Customer
from apps.inventory.models import InventoryBatch, StockMovement
from apps.payments.models import LedgerEntry, PartyType, Payment
from apps.purchases.models import Purchase
from apps.purchases.services import purchase_service
from apps.sales.models import Sale
from apps.sales.services import invoice_payload_service, sale_service
from tests.factories import CatalogFactory


@pytest.mark.django_db
class TestDocumentNumbering:
    def test_unique_sequential_sale_numbers(self) -> None:
        first = document_number_service.next_number("SALE")
        second = document_number_service.next_number("SALE")
        assert first != second
        assert DocumentSequence.objects.filter(document_type="SALE").count() == 1


@pytest.mark.django_db
class TestPurchasePosting:
    def test_purchase_creates_batch_stock_and_vendor_balance(self) -> None:
        product = CatalogFactory.product(sku="P3-CABLE")
        vendor = CatalogFactory.vendor("Phase3 Vendor")
        purchase = purchase_service.create_purchase(
            {
                "vendor_id": vendor.id,
                "amount_paid": "0",
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "10",
                        "base_purchase_price": "100.00",
                        "selling_price": "150.00",
                        "safe_selling_price": "130.00",
                        "maximum_discount_percent": "5",
                        "pricing_confirmed": True,
                    }
                ],
            }
        )
        vendor.refresh_from_db()
        batch = InventoryBatch.objects.get(product=product)
        assert purchase.grand_total > 0
        assert batch.remaining_quantity == Decimal("10")
        assert StockMovement.objects.filter(batch=batch).exists()
        assert vendor.current_balance == purchase.grand_total
        assert LedgerEntry.objects.filter(party_type=PartyType.VENDOR, party_id=vendor.id).exists()

    def test_previous_batch_is_not_overwritten(self) -> None:
        product = CatalogFactory.product(sku="P3-PREV")
        vendor = CatalogFactory.vendor("Prev Vendor")
        payload = lambda cost, qty: {
            "vendor_id": vendor.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": qty,
                    "base_purchase_price": cost,
                    "selling_price": "140",
                    "safe_selling_price": "110",
                    "maximum_discount_percent": "0",
                    "pricing_mode": "NEW",
                    "pricing_confirmed": True,
                }
            ],
        }
        purchase_service.create_purchase(payload("80", "5"))
        first_cost = InventoryBatch.objects.get(product=product).purchase_cost
        purchase_service.create_purchase(payload("90", "3"))
        lots = list(InventoryBatch.objects.filter(product=product).order_by("id"))
        assert len(lots) == 2
        assert lots[0].purchase_cost == first_cost
        assert lots[0].remaining_quantity == Decimal("5")

    def test_purchase_rollback_leaves_no_stock(self) -> None:
        product = CatalogFactory.product(sku="P3-ROLL")
        vendor = CatalogFactory.vendor("Rollback Vendor")
        with pytest.raises(ValidationError):
            purchase_service.create_purchase(
                {
                    "vendor_id": vendor.id,
                    "items": [
                        {
                            "product_id": product.id,
                            "quantity": "0",
                            "base_purchase_price": "10",
                            "selling_price": "20",
                            "safe_selling_price": "15",
                            "maximum_discount_percent": "0",
                            "pricing_confirmed": True,
                        }
                    ],
                }
            )
        assert Purchase.objects.count() == 0
        assert InventoryBatch.objects.filter(product=product).count() == 0
        vendor.refresh_from_db()
        assert vendor.current_balance == 0


@pytest.mark.django_db
class TestSalePosting:
    def _stocked(self, sku: str = "P3-SALE", qty: str = "10"):
        product = CatalogFactory.product(sku=sku)
        vendor = CatalogFactory.vendor(f"V-{sku}")
        purchase_service.create_purchase(
            {
                "vendor_id": vendor.id,
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": qty,
                        "base_purchase_price": "50",
                        "selling_price": "100",
                        "safe_selling_price": "80",
                        "maximum_discount_percent": "10",
                        "pricing_confirmed": True,
                    }
                ],
            }
        )
        return product, vendor

    def test_sale_reduces_stock_and_numbers_invoice(self) -> None:
        product, _vendor = self._stocked()
        customer = Customer.objects.create(name="Walk Buyer", customer_type=CatalogFactory.customer_type())
        sale = sale_service.create_sale(
            {
                "customer_id": customer.id,
                "payment_method": "CASH",
                "amount_paid": "1180",
                "items": [{"product_id": product.id, "quantity": "2", "unit_price": "100"}],
            }
        )
        assert sale.invoice_number
        assert InventoryBatch.objects.get(product=product).remaining_quantity == Decimal("8")
        customer.refresh_from_db()
        assert customer.current_balance == Decimal("0")
        payload = invoice_payload_service.for_sale(sale)
        assert payload["invoice_number"] == sale.invoice_number

    def test_fifo_across_batches(self) -> None:
        product = CatalogFactory.product(sku="P3-FIFO")
        vendor = CatalogFactory.vendor("FIFO Vendor")
        line = lambda qty, cost: {
            "product_id": product.id,
            "quantity": qty,
            "base_purchase_price": cost,
            "selling_price": "20",
            "safe_selling_price": "12",
            "maximum_discount_percent": "0",
            "pricing_confirmed": True,
        }
        purchase_service.create_purchase({"vendor_id": vendor.id, "items": [line("5", "10")]})
        purchase_service.create_purchase({"vendor_id": vendor.id, "items": [line("8", "11")]})
        sale = sale_service.create_sale(
            {
                "payment_method": "CASH",
                "amount_paid": "9999",
                "items": [{"product_id": product.id, "quantity": "7", "unit_price": "20"}],
            }
        )
        lots = list(InventoryBatch.objects.filter(product=product).order_by("id"))
        assert lots[0].remaining_quantity == Decimal("0")
        assert lots[1].remaining_quantity == Decimal("6")
        assert sale.items.count() == 2

    def test_sale_can_pick_a_specific_lot(self) -> None:
        product, vendor = self._stocked(qty="5")
        purchase_service.create_purchase(
            {
                "vendor_id": vendor.id,
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "8",
                        "base_purchase_price": "11",
                        "selling_price": "25",
                        "safe_selling_price": "20",
                        "maximum_discount_percent": "5",
                        "pricing_confirmed": True,
                    }
                ],
            }
        )
        newer = InventoryBatch.objects.filter(product=product).order_by("id").last()
        sale = sale_service.create_sale(
            {
                "payment_method": "CASH",
                "amount_paid": "9999",
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "3",
                        "unit_price": "25",
                        "batch_id": newer.id,
                    }
                ],
            }
        )
        lots = list(InventoryBatch.objects.filter(product=product).order_by("id"))
        assert lots[0].remaining_quantity == Decimal("5")
        assert lots[1].remaining_quantity == Decimal("5")
        assert sale.items.count() == 1
        assert sale.items.first().batch_id == newer.id

    def test_sale_rollback_on_insufficient_stock(self) -> None:
        product, _vendor = self._stocked(qty="2")
        with pytest.raises(ValidationError):
            sale_service.create_sale(
                {
                    "payment_method": "CASH",
                    "amount_paid": "1",
                    "items": [{"product_id": product.id, "quantity": "9", "unit_price": "100"}],
                }
            )
        assert Sale.objects.count() == 0
        assert InventoryBatch.objects.get(product=product).remaining_quantity == Decimal("2")

    def test_partial_and_credit_balances(self) -> None:
        product, _vendor = self._stocked()
        customer = Customer.objects.create(name="Credit Co", customer_type=CatalogFactory.customer_type("c", "C"))
        sale = sale_service.create_sale(
            {
                "customer_id": customer.id,
                "payment_method": "CREDIT",
                "amount_paid": "0",
                "items": [{"product_id": product.id, "quantity": "1", "unit_price": "100"}],
            }
        )
        customer.refresh_from_db()
        assert sale.payment_status == "CREDIT"
        assert customer.current_balance == sale.grand_total
        partial = sale_service.create_sale(
            {
                "customer_id": customer.id,
                "payment_method": "UPI",
                "amount_paid": "50",
                "items": [{"product_id": product.id, "quantity": "1", "unit_price": "100"}],
            }
        )
        customer.refresh_from_db()
        assert partial.payment_status == "PARTIAL"
        assert customer.current_balance == sale.grand_total + partial.grand_total - Decimal("50")

    def test_safe_price_warning_and_override(self) -> None:
        product, _vendor = self._stocked()
        with pytest.raises(ValidationError) as exc:
            sale_service.create_sale(
                {
                    "payment_method": "CASH",
                    "amount_paid": "10",
                    "items": [{"product_id": product.id, "quantity": "1", "unit_price": "10"}],
                }
            )
        assert "SAFE_PRICE_WARNING" in str(exc.value.detail)
        sale = sale_service.create_sale(
            {
                "payment_method": "CASH",
                "amount_paid": "10",
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "1",
                        "unit_price": "10",
                        "below_safe_override": True,
                    }
                ],
            }
        )
        assert sale.items.first().below_safe_override is True
        assert AuditLog.objects.filter(action="safe_price_override").exists()


@pytest.mark.django_db
class TestReturnsAndApi:
    def test_sale_and_purchase_returns(self) -> None:
        product = CatalogFactory.product(sku="P3-RET")
        vendor = CatalogFactory.vendor("Return Vendor")
        purchase = purchase_service.create_purchase(
            {
                "vendor_id": vendor.id,
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "10",
                        "base_purchase_price": "40",
                        "selling_price": "80",
                        "safe_selling_price": "60",
                        "maximum_discount_percent": "0",
                        "pricing_confirmed": True,
                    }
                ],
            }
        )
        customer = Customer.objects.create(name="Ret Cust", customer_type=CatalogFactory.customer_type("r", "R"))
        sale = sale_service.create_sale(
            {
                "customer_id": customer.id,
                "payment_method": "CREDIT",
                "amount_paid": "0",
                "items": [{"product_id": product.id, "quantity": "4", "unit_price": "80"}],
            }
        )
        sale_item = sale.items.first()
        sale_service.create_return(sale, [{"sale_item_id": sale_item.id, "quantity": "2"}])
        assert Sale.objects.filter(pk=sale.pk).exists()
        batch = InventoryBatch.objects.get(product=product)
        batch.refresh_from_db()
        assert batch.remaining_quantity == Decimal("8")
        purchase_item = purchase.items.first()
        purchase_service.create_return(purchase, [{"purchase_item_id": purchase_item.id, "quantity": "1"}])
        assert Purchase.objects.filter(pk=purchase.pk).exists()
        batch.refresh_from_db()
        assert batch.remaining_quantity == Decimal("7")

    def test_http_purchase_sale_payment_and_ledgers(self, auth_client) -> None:
        product = CatalogFactory.product(sku="P3-API")
        vendor = CatalogFactory.vendor("API Vendor")
        customer = Customer.objects.create(name="API Cust", customer_type=CatalogFactory.customer_type("a", "A"))
        buy = auth_client.post(
            "/api/v1/purchases/",
            {
                "vendor_id": vendor.id,
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "6",
                        "base_purchase_price": "25",
                        "selling_price": "40",
                        "safe_selling_price": "30",
                        "maximum_discount_percent": "0",
                        "pricing_confirmed": True,
                    }
                ],
            },
            content_type="application/json",
        )
        assert buy.status_code == 201
        sell = auth_client.post(
            "/api/v1/sales/",
            {
                "customer_id": customer.id,
                "payment_method": "CASH",
                "amount_paid": "0",
                "items": [{"product_id": product.id, "quantity": "1", "unit_price": "40"}],
            },
            content_type="application/json",
        )
        assert sell.status_code == 201
        sale_id = sell.json()["id"]
        invoice = auth_client.get(f"/api/v1/sales/{sale_id}/invoice/")
        assert invoice.status_code == 200
        pay = auth_client.post(
            "/api/v1/payments/",
            {
                "party_type": "CUSTOMER",
                "party_id": customer.id,
                "amount": "10",
                "method": "UPI",
            },
            content_type="application/json",
        )
        assert pay.status_code == 201
        ledger = auth_client.get(f"/api/v1/customers/{customer.id}/ledger/")
        assert ledger.status_code == 200
        assert len(ledger.json()["entries"]) >= 2
        vledger = auth_client.get(f"/api/v1/vendors/{vendor.id}/ledger/")
        assert vledger.status_code == 200
        assert Payment.objects.count() >= 1
