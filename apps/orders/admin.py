from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "name", "size", "quantity", "unit_price", "image_url")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ("order_id", "customer_email", "customer_name", "total", "payment_method", "status", "created_at")
    list_filter = ("status", "payment_method")
    list_editable = ("status",)
    search_fields = ("order_id", "customer_email", "customer_name")
    readonly_fields = ("order_id", "user", "customer_email", "total", "payment_method", "created_at", "updated_at")
