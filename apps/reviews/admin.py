from django.contrib import admin
from django.utils import timezone

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "author_name", "rating", "has_reply", "created_at")
    list_filter = ("rating", "product")
    search_fields = ("author_name", "comment", "product__name")
    readonly_fields = ("product", "user", "author_name", "rating", "comment", "replied_at", "created_at")
    fields = ("product", "user", "author_name", "rating", "comment", "admin_reply", "replied_at", "created_at")

    @admin.display(boolean=True, description="Replied")
    def has_reply(self, obj):
        return bool(obj.admin_reply)

    def save_model(self, request, obj, form, change):
        if "admin_reply" in form.changed_data:
            obj.admin_reply = (obj.admin_reply or "").strip() or None
            obj.replied_at = timezone.now() if obj.admin_reply else None
        super().save_model(request, obj, form, change)
