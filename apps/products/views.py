from django.db.models import Q
from rest_framework import viewsets

from apps.accounts.permissions import IsAdminOrReadOnly

from .models import Product
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    /api/products/       GET  public catalog (?category=, ?search=, ?in_stock=1)
                         POST admin: create
    /api/products/<id>/  GET  public; PUT/PATCH/DELETE admin
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = Product.objects.prefetch_related("stock").order_by("created_at")
        params = self.request.query_params
        if category := params.get("category", "").strip():
            qs = qs.filter(category__iexact=category)
        if search := params.get("search", "").strip():
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if params.get("in_stock") in {"1", "true"}:
            qs = qs.filter(stock__quantity__gt=0).distinct()
        return qs

