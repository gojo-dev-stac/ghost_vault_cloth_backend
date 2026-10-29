from django.contrib import admin

from .models import Product, ProductStock


class ProductStockInline(admin.TabularInline):
    model = ProductStock
    extra = 0
    max_num = 4


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductStockInline]
    list_display = ("name", "category", "price", "stock_summary", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "description")

    @admin.display(description="Stock (S/M/L/XL)")
    def stock_summary(self, obj):
        sizes = obj.sizes
        return " / ".join(str(sizes[s]) for s in ("S", "M", "L", "XL"))
