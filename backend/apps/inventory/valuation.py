"""
Inventory valuation strategies.

Phase 2 uses FIFO (oldest open batch first) for on-hand value.
Weighted average can be selected later via ApplicationSettings.inventory_valuation_method.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from apps.inventory.models import InventoryBatch
from apps.products.models import Product


class ValuationStrategy(Protocol):
    """Plug-in interface for on-hand inventory value."""

    code: str

    def value_on_hand(self, product: Product) -> Decimal: ...


class FifoValuation:
    """Sum remaining_quantity * purchase_cost across lots, oldest first."""

    code = "FIFO"

    def value_on_hand(self, product: Product) -> Decimal:
        lots = InventoryBatch.objects.filter(product=product, remaining_quantity__gt=0).order_by(
            "purchase_date",
            "id",
        )
        return sum(map(lambda lot: lot.remaining_quantity * lot.purchase_cost, lots), Decimal("0"))


class WeightedAverageValuation:
    """Average remaining cost, then multiply by remaining quantity."""

    code = "WEIGHTED_AVERAGE"

    def value_on_hand(self, product: Product) -> Decimal:
        lots = InventoryBatch.objects.filter(product=product, remaining_quantity__gt=0)
        qty = sum(map(lambda lot: lot.remaining_quantity, lots), Decimal("0"))
        cost = sum(map(lambda lot: lot.remaining_quantity * lot.purchase_cost, lots), Decimal("0"))
        if qty == 0:
            return Decimal("0")
        return (cost / qty) * qty


class ValuationService:
    """Resolve the shop's configured strategy. Default is FIFO."""

    def __init__(self) -> None:
        self._registry: dict[str, ValuationStrategy] = {
            "FIFO": FifoValuation(),
            "WEIGHTED_AVERAGE": WeightedAverageValuation(),
        }

    def strategy(self, code: str | None = None) -> ValuationStrategy:
        key = (code or "FIFO").upper()
        return self._registry.get(key, self._registry["FIFO"])

    def value_on_hand(self, product: Product, *, method: str | None = None) -> Decimal:
        return self.strategy(method).value_on_hand(product)


valuation_service = ValuationService()
