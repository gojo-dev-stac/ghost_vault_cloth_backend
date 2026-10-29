from rest_framework import serializers

from apps.products.models import Size

from .models import Order, OrderItem



class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(read_only=True, allow_null=True)
    price = serializers.DecimalField(source="unit_price", max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = OrderItem
        fields = ["product_id", "name", "size", "quantity", "price", "image_url"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_id",
            "customer_email",
            "customer_name",
            "shipping",
            "items",
            "total",
            "payment_method",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderLineInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    size = serializers.ChoiceField(choices=Size.choices)
    quantity = serializers.IntegerField(min_value=1, max_value=50)


class CustomerInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    firstName = serializers.CharField(max_length=100, required=False, allow_blank=True)
    lastName = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    address1 = serializers.CharField(max_length=300, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    province = serializers.CharField(max_length=100, required=False, allow_blank=True)
    zip = serializers.CharField(max_length=20, required=False, allow_blank=True)
    countryCode = serializers.CharField(max_length=2, required=False, allow_blank=True)


class PlaceOrderSerializer(serializers.Serializer):
    """POST body: {items: [{product_id, size, quantity}], payment_method, customer: {...}}"""

    items = OrderLineInputSerializer(many=True, allow_empty=False)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    customer = CustomerInputSerializer(required=False, default=dict)

    def validate_items(self, value):
        if len(value) > 50:
            raise serializers.ValidationError("Too many items in one order.")
        return value


class OrderStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)

    class Meta:
        model = Order
        fields = ["status"]
