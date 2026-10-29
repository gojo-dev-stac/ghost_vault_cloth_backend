from django.db import transaction
from rest_framework import serializers

from .models import SIZES, Product


class SizeStockField(serializers.Field):
    """Per-size stock as {"S": 3, "M": 5, "L": 8, "XL": 2}."""

    default_error_messages = {
        "invalid": 'Expected an object like {"S": 0, "M": 0, "L": 0, "XL": 0}.',
        "bad_size": "Unknown size {size}; use one of S, M, L, XL.",
        "bad_qty": "Stock for {size} must be a whole number from 0 to 100000.",
    }

    def to_representation(self, product):
        return product.sizes

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            self.fail("invalid")
        sizes = {}
        for size, qty in data.items():
            if size not in SIZES:
                self.fail("bad_size", size=size)
            if isinstance(qty, bool) or not str(qty).strip().isdigit() or int(qty) > 100_000:
                self.fail("bad_qty", size=size)
            sizes[size] = int(qty)
        # source="*" merges this dict into validated_data
        return {"sizes": sizes}


class ProductSerializer(serializers.ModelSerializer):
    sizes = SizeStockField(source="*")
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, coerce_to_string=False)
    total_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "image_url",
            "sizes",
            "total_stock",
            "category",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_stock(self, product) -> int:
        return sum(product.sizes.values())

    def validate_image_url(self, value):
        value = (value or "").strip()
        if not value:
            return None
        if not (value.startswith(("https://", "http://", "/"))):
            raise serializers.ValidationError("Use an absolute URL (https://…) or a site path (/…).")
        return value

    @transaction.atomic
    def create(self, validated_data):
        sizes = validated_data.pop("sizes", {})
        product = Product.objects.create(**validated_data)
        product.set_sizes({size: sizes.get(size, 0) for size in SIZES})
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        sizes = validated_data.pop("sizes", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if sizes is not None:
            instance.set_sizes(sizes)
        return instance
