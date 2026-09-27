"""Product catalog writes go through this service so aliases, tags, and audit stay together."""

from __future__ import annotations

import re

from django.db import transaction

from apps.core.services import audit_service
from apps.products.models import Product, ProductAlias


class SkuSuggestionService:
    """
    Build unique SKU suggestions from a product name.

    Example: "Conduit Pipes" → "CP-00012" (initials + next free serial for that prefix).
    """

    SKIP_WORDS = frozenset({"and", "or", "of", "the", "for", "a", "an", "to", "with"})
    SERIAL_WIDTH = 5
    MAX_PREFIX_LEN = 4

    def prefix_from_name(self, name: str) -> str:
        """Derive a short uppercase letter prefix from significant words in the name."""
        tokens = [
            token
            for token in re.findall(r"[A-Za-z0-9]+", name or "")
            if token.lower() not in self.SKIP_WORDS
        ]
        if not tokens:
            return "SKU"
        if len(tokens) == 1:
            word = re.sub(r"[^A-Za-z]", "", tokens[0]).upper()
            if not word:
                return "SKU"
            return (word[:3] if len(word) >= 3 else word.ljust(2, "X"))[: self.MAX_PREFIX_LEN]
        initials = "".join(map(lambda token: re.sub(r"[^A-Za-z0-9]", "", token)[:1], tokens))
        letters = re.sub(r"[^A-Za-z]", "", initials).upper()
        if not letters:
            return "SKU"
        return letters[: self.MAX_PREFIX_LEN]

    def suggest(self, name: str) -> dict[str, str | int]:
        """
        Return the next unused SKU for this name's prefix.

        Scans existing SKUs matching PREFIX-NNNN so suggestions stay unique even if
        numbers were entered manually earlier.
        """
        prefix = self.prefix_from_name(name)
        loose = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
        existing = Product.objects.filter(sku__istartswith=f"{prefix}-").values_list("sku", flat=True)
        highest = 0
        for sku in existing:
            matched = loose.match(sku or "")
            if matched:
                highest = max(highest, int(matched.group(1)))
        next_value = highest + 1
        width = max(self.SERIAL_WIDTH, len(str(next_value)))
        candidate = f"{prefix}-{next_value:0{width}d}"
        # Guard against residual collision (case variants, concurrent creates).
        while Product.objects.filter(sku__iexact=candidate).exists():
            next_value += 1
            width = max(self.SERIAL_WIDTH, len(str(next_value)))
            candidate = f"{prefix}-{next_value:0{width}d}"
        return {
            "sku": candidate,
            "prefix": prefix,
            "serial": next_value,
            "name": name.strip(),
        }


class ProductService:
    """Create and update products with optional search aliases."""

    @transaction.atomic
    def create_product(self, *, product: Product, alias_terms: list[str] | None = None) -> Product:
        """Save a product and attach unique alias terms in one transaction."""
        product.save()
        self.replace_aliases(product=product, alias_terms=alias_terms or [])
        audit_service.record(
            action="product_create",
            entity="product",
            entity_id=product.pk,
            new_data={"sku": product.sku, "name": product.name},
        )
        return product

    @transaction.atomic
    def replace_aliases(self, *, product: Product, alias_terms: list[str]) -> None:
        """Replace alias terms for a product. Empty strings are ignored."""
        unique_terms = list(dict.fromkeys(map(lambda term: term.strip().lower(), alias_terms)))
        unique_terms = list(filter(lambda term: bool(term), unique_terms))
        ProductAlias.objects.filter(product=product).exclude(term__in=unique_terms).delete()
        existing = set(ProductAlias.objects.filter(product=product).values_list("term", flat=True))
        list(
            map(
                lambda term: ProductAlias.objects.create(product=product, term=term)
                if term not in existing
                else None,
                unique_terms,
            )
        )


product_service = ProductService()
sku_suggestion_service = SkuSuggestionService()
