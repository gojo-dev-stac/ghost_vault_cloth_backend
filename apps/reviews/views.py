import uuid

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsApprovedMember

from .models import Review
from .serializers import ReviewReplySerializer, ReviewSerializer


class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/reviews/             GET   public (?product=<id>, ?unreplied=1)
                              POST  approved members: {product_id, rating, comment}
    /api/reviews/<id>/        GET   public; DELETE admin (moderation)
    /api/reviews/<id>/reply/  PATCH admin: {"reply": "..."} ("" removes the reply)
    """

    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "create":
            return [IsApprovedMember()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = Review.objects.order_by("-created_at")
        params = self.request.query_params
        if product := params.get("product"):
            try:
                qs = qs.filter(product_id=uuid.UUID(product))
            except ValueError:
                return qs.none()
        if params.get("unreplied") in {"1", "true"}:
            qs = qs.filter(admin_reply__isnull=True)
        return qs

    @action(detail=True, methods=["patch"])
    def reply(self, request, pk=None):
        review = self.get_object()
        serializer = ReviewReplySerializer(review, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ReviewSerializer(review, context=self.get_serializer_context()).data)
