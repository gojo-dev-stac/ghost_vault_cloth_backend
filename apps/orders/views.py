from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsApprovedMember

from .models import Order
from .serializers import OrderSerializer, OrderStatusSerializer, PlaceOrderSerializer
from .services import place_order


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/orders/                  GET   members: own orders; admin: all (?mine=1 for own, ?status=)
                                  POST  approved members: place an order
    /api/orders/<id>/             GET   order detail (own, or any for admin)
    /api/orders/<id>/status/      PATCH admin: {"status": "Confirmed"}
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "create":
            return [IsApprovedMember()]
        if self.action == "set_status":
            return [IsAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.prefetch_related("items").order_by("-created_at")
        if not user.is_admin or self.request.query_params.get("mine") in {"1", "true"}:
            qs = qs.filter(user=user)
        if (status_filter := self.request.query_params.get("status")) in Order.Status.values:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request):
        serializer = PlaceOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = place_order(
            user=request.user,
            items=data["items"],
            payment_method=data["payment_method"],
            customer=dict(data["customer"]),
        )
        order = Order.objects.prefetch_related("items").get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="status")
    def set_status(self, request, pk=None):
        order = self.get_object()
        serializer = OrderStatusSerializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderSerializer(order).data)
