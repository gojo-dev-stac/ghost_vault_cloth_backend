from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import IsAdmin

from .emails import send_reply_email
from .models import Complaint
from .serializers import ComplaintReplySerializer, ComplaintSerializer, ComplaintStatusSerializer


class ComplaintViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/contact/              POST  anyone: {name, email, subject, message}
                               GET   admin: inbox (?status=Open|Replied|Closed); members: their own messages
    /api/contact/<id>/         GET   admin or the member who sent it
    /api/contact/<id>/reply/   PATCH admin: {"reply": "...", "send_email": true} -> status Replied
    /api/contact/<id>/status/  PATCH admin: {"status": "Closed"}
    """

    serializer_class = ComplaintSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        if self.action in {"reply", "set_status"}:
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "contact"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        user = self.request.user
        qs = Complaint.objects.order_by("-created_at")
        if not user.is_admin:
            qs = qs.filter(user=user)
        if (status_filter := self.request.query_params.get("status")) in Complaint.Status.values:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request):
        serializer = ComplaintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        complaint = serializer.save(user=user)
        return Response(ComplaintSerializer(complaint).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"])
    def reply(self, request, pk=None):
        complaint = self.get_object()
        serializer = ComplaintReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complaint.admin_reply = serializer.validated_data["reply"].strip()
        complaint.replied_at = timezone.now()
        complaint.status = Complaint.Status.REPLIED
        complaint.save(update_fields=["admin_reply", "replied_at", "status", "updated_at"])
        if serializer.validated_data["send_email"]:
            send_reply_email(complaint)
        return Response(ComplaintSerializer(complaint).data)

    @action(detail=True, methods=["patch"], url_path="status")
    def set_status(self, request, pk=None):
        complaint = self.get_object()
        serializer = ComplaintStatusSerializer(complaint, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ComplaintSerializer(complaint).data)
