from django.db.models import Q
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .emails import send_password_reset_email
from .models import Profile, User
from .permissions import IsAdmin
from .serializers import (
    AdminMemberSerializer,
    LoginSerializer,
    LogoutSerializer,
    MemberSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    RegisterSerializer,
    check_can_manage,
    tokens_for,
)


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class RegisterView(AuthThrottleMixin, generics.CreateAPIView):
    """POST /api/auth/register/ — request vault access (profile starts pending)."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({**tokens_for(user), "user": MemberSerializer(user).data}, status=status.HTTP_201_CREATED)


class LoginView(AuthThrottleMixin, TokenObtainPairView):
    """POST /api/auth/login/ — {email, password} -> {access, refresh, user}."""

    serializer_class = LoginSerializer


class RefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/ — {refresh} -> {access, refresh} (refresh tokens rotate)."""

    serializer_class = RefreshSerializer


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the refresh token."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            pass  # already expired/blacklisted: the session is over either way
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — current member; only display_name is editable."""

    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return User.objects.select_related("profile").get(pk=self.request.user.pk)


class PasswordChangeView(APIView):
    """POST /api/auth/password/change/ — signed-in member changes their password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})


class PasswordResetRequestView(AuthThrottleMixin, APIView):
    """POST /api/auth/password/reset/ — email a reset link (always 200, no account enumeration)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user:
            send_password_reset_email(user)
        return Response({"detail": "If that email has an account, a reset link is on its way."})


class PasswordResetConfirmView(AuthThrottleMixin, APIView):
    """POST /api/auth/password/reset/confirm/ — {uid, token, new_password}."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated. You can sign in now."})


class AdminMemberViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/auth/members/            GET    list (?status=pending|approved|rejected, ?search=)
    /api/auth/members/<user_id>/  GET    one member
    /api/auth/members/<user_id>/  PATCH  {"status": "approved"|"rejected"|"pending"}; owner only: {"is_admin": bool}
    /api/auth/members/<user_id>/  DELETE remove the account

    The owner can never be changed or deleted, nobody can change or delete
    themselves here, and only the owner can manage other admins.
    """

    serializer_class = AdminMemberSerializer
    permission_classes = [IsAdmin]
    lookup_field = "user_id"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        check_can_manage(self.request.user, instance.user)
        instance.user.delete()  # the profile goes with it

    def get_queryset(self):
        qs = Profile.objects.select_related("user", "reviewed_by").order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter in Profile.Status.values:
            qs = qs.filter(status=status_filter)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(user__email__icontains=search) | Q(user__display_name__icontains=search))
        return qs
