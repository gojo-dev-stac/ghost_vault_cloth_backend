"""
Products: the GHOST catalog with stock tracked per size (S / M / L / XL).

Stock lives in ProductStock rows (one per product and size) so it can be
decremented atomically with a conditional UPDATE when an order is placed.
"""
import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class Size(models.TextChoices):
    S = "S", "S"
    M = "M", "M"
    L = "L", "L"
    XL = "XL", "XL"


SIZES = [s.value for s in Size]


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    image_url = models.CharField(max_length=500, blank=True, null=True)
    category = models.CharField(max_length=100, default="Hoodies", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_non_negative")]

    def __str__(self):
        return self.name

    @property
    def sizes(self) -> dict[str, int]:
        """{"S": n, "M": n, "L": n, "XL": n}; uses prefetched stock when available."""
        stock = {size: 0 for size in SIZES}
        for row in self.stock.all():
            stock[row.size] = row.quantity
        return stock

    @property
    def total_stock(self) -> int:
        return self.stock.aggregate(total=Sum("quantity"))["total"] or 0

    def set_sizes(self, sizes: dict[str, int]) -> None:
        for size in SIZES:
            if size in sizes:
                ProductStock.objects.update_or_create(product=self, size=size, defaults={"quantity": sizes[size]})


class ProductStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock")
    size = models.CharField(max_length=2, choices=Size.choices)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["product", "size"]
        constraints = [
            models.UniqueConstraint(fields=["product", "size"], name="unique_product_size"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="stock_non_negative"),
        ]

    def __str__(self):
        return f"{self.product.name} / {self.size}: {self.quantity}"
