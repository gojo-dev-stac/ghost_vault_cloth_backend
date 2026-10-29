"""Order placement: the Django replacement for the `place_order` Postgres RPC."""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.products.models import Product, ProductStock

from .models import Order, OrderItem


@transaction.atomic
def place_order(*, user, items: list[dict], payment_method: str, customer: dict) -> Order:
    """
    Create an order for an approved member.

    - prices always come from the database, never from the client
    - stock is decremented with a conditional UPDATE (quantity >= requested),
      so two concurrent checkouts can never oversell a size
    - any failure rolls back the whole order, stock included
    """
    if not user.can_shop:
        raise PermissionDenied("Your vault access has not been approved yet.")

    # Merge duplicate lines so the stock check sees the full requested quantity.
    wanted: dict[tuple, int] = defaultdict(int)
    for item in items:
        wanted[(item["product_id"], item["size"])] += item["quantity"]

    # Lock in primary-key order so concurrent checkouts can't deadlock.
    locked = Product.objects.select_for_update().filter(pk__in={pid for pid, _ in wanted}).order_by("pk")
    products = {p.pk: p for p in locked}

    order = Order.objects.create(
        user=user,
        customer_email=user.email,
        customer_name=customer.get("name", "").strip() or user.display_name,
        shipping=customer,
        total=Decimal("0"),
        payment_method=payment_method,
    )

    total = Decimal("0")
    for (product_id, size), quantity in wanted.items():
        product = products.get(product_id)
        if product is None:
            raise ValidationError({"items": ["A product in your bag is no longer available."]})

        updated = ProductStock.objects.filter(product=product, size=size, quantity__gte=quantity).update(
            quantity=F("quantity") - quantity
        )
        if not updated:
            left = ProductStock.objects.filter(product=product, size=size).values_list("quantity", flat=True).first()
            raise ValidationError({"items": [f"{product.name} size {size} has only {left or 0} left."]})

        OrderItem.objects.create(
            order=order,
            product=product,
            name=product.name,
            size=size,
            quantity=quantity,
            unit_price=product.price,
            image_url=product.image_url,
        )
        total += product.price * quantity

    order.total = total
    order.save(update_fields=["total"])
    return order
