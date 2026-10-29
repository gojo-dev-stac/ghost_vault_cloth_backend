"""
Orders: placed by approved members, fulfilled by the admin.

Status moves Pending → Confirmed → Processing → Shipped → Delivered.
Each OrderItem keeps a snapshot of the product name, price and image so
history stays correct when the catalog changes or a product is deleted.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models

from apps.products.models import Size


def generate_order_id() -> str:
    return f"GV-{secrets.token_hex(4).upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending"
        CONFIRMED = "Confirmed"
        PROCESSING = "Processing"
        SHIPPED = "Shipped"
        DELIVERED = "Delivered"

    class PaymentMethod(models.TextChoices):
        COD = "COD", "Cash on delivery"
        STRIPE = "Stripe", "Stripe"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=20, unique=True, default=generate_order_id, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="orders")
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=200, blank=True)
    shipping = models.JSONField(default=dict, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_id


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.SET_NULL, null=True, related_name="+")
    name = models.CharField(max_length=200)
    size = models.CharField(max_length=2, choices=Size.choices)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} × {self.name} ({self.size})"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
