from django.utils import timezone
from rest_framework import serializers

from apps.products.models import Product

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "product_id",
            "author_name",
            "rating",
            "comment",
            "admin_reply",
            "replied_at",
            "created_at",
            "is_mine",
        ]
        read_only_fields = ["id", "author_name", "admin_reply", "replied_at", "created_at", "is_mine"]

    def get_is_mine(self, review) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and review.user_id == request.user.pk)

    def validate_comment(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Write a few words about the piece.")
        return value

    def create(self, validated_data):
        # Author and reply are always set server-side, never from the client.
        user = self.context["request"].user
        author = user.display_name.strip() or user.email.split("@")[0]
        return Review.objects.create(user=user, author_name=author[:100], **validated_data)


class ReviewReplySerializer(serializers.ModelSerializer):
    """Admin reply; an empty reply removes it."""

    reply = serializers.CharField(source="admin_reply", max_length=2000, allow_blank=True, trim_whitespace=True)

    class Meta:
        model = Review
        fields = ["reply"]

    def update(self, instance, validated_data):
        reply = validated_data["admin_reply"].strip()
        instance.admin_reply = reply or None
        instance.replied_at = timezone.now() if reply else None
        instance.save(update_fields=["admin_reply", "replied_at"])
        return instance
