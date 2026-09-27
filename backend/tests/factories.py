"""
Shared factories for Phase 1 model and API tests.

Each helper is a class method so tests stay object-oriented rather than loose
module-level functions.
"""

from __future__ import annotations

from decimal import Decimal

from apps.customers.models import CustomerType
from apps.products.models import Brand, Category, Product, Unit
from apps.vendors.models import Vendor


class CatalogFactory:
    """Build the minimum graph a Product row requires."""

    @staticmethod
    def category(name: str = "Wires") -> Category:
        obj, _created = Category.objects.get_or_create(name=name)
        return obj

    @staticmethod
    def brand(name: str = "Polycab") -> Brand:
        obj, _created = Brand.objects.get_or_create(name=name)
        return obj

    @staticmethod
    def unit(name: str = "Metre", abbreviation: str = "m") -> Unit:
        obj, _created = Unit.objects.get_or_create(name=name, defaults={"abbreviation": abbreviation})
        return obj

    @classmethod
    def product(cls, sku: str = "WIRE-25") -> Product:
        return Product.objects.create(
            name="Polycab 2.5 sq mm FR House Wire",
            sku=sku,
            category=cls.category(),
            brand=cls.brand(),
            unit=cls.unit(),
            gst_rate=Decimal("18.00"),
            mrp=Decimal("2100.00"),
            default_selling_price=Decimal("1900.00"),
            default_safe_selling_price=Decimal("1750.00"),
        )

    @staticmethod
    def vendor(name: str = "ABC Traders") -> Vendor:
        return Vendor.objects.create(name=name, phone="9999999999")

    @staticmethod
    def customer_type(code: str = "retail", name: str = "Retail") -> CustomerType:
        row, _created = CustomerType.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})
        return row
