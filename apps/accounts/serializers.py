from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import rejected_error
from .models import Profile, User


class MemberSerializer(serializers.ModelSerializer):
    """The signed-in member as the React app sees it (mirrors the old `Member` type)."""

    status = serializers.CharField(source="profile.status", read_only=True)
    created_at = serializers.DateTimeField(source="profile.created_at", read_only=True)
    is_admin = serializers.BooleanField(read_only=True)
    is_owner = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "status", "created_at", "is_admin", "is_owner"]
        read_only_fields = ["id", "email", "status", "created_at", "is_admin", "is_owner"]


def tokens_for(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password -> {access, refresh, user}."""

    def validate(self, attrs):
        attrs[self.username_field] = attrs[self.username_field].strip().lower()
        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            # Right password but a rejected account: say so instead of "no active account".
            if getattr(self, "user", None) is not None and self.user.is_rejected:
                raise rejected_error()
            raise
        data["user"] = MemberSerializer(self.user).data
        return data


class RefreshSerializer(TokenRefreshSerializer):
    """Token refresh that reports a rejected account with its own code."""

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            # simplejwt looks the user up with .get(); a deleted account must be a 401, not a 500.
            raise AuthenticationFailed(self.error_messages["no_active_account"], "no_active_account")
        except AuthenticationFailed:
            token = RefreshToken(attrs["refresh"], verify=False)
            user = User.objects.filter(pk=token.payload.get(api_settings.USER_ID_CLAIM)).first()
            if user is not None and user.is_rejected:
                raise rejected_error()
            raise


class RegisterSerializer(serializers.Serializer):
    """Request access: creates a member whose profile starts as pending."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    display_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        candidate = User(email=attrs["email"], display_name=attrs.get("display_name", ""))
        password_validation.validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            display_name=validated_data.get("display_name", "").strip(),
        )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, user=self.context["request"].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    default_error = "This reset link is invalid or has expired."

    def validate(self, attrs):
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=pk, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": self.default_error})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": self.default_error})
        try:
            password_validation.validate_password(attrs["new_password"], user=user)
        except Exception as exc:  # django ValidationError -> DRF field error
            raise serializers.ValidationError({"new_password": list(getattr(exc, "messages", [str(exc)]))})
        attrs["user"] = user
        return attrs


class AdminMemberSerializer(serializers.ModelSerializer):
    """Member row for the admin dashboard. Writable: `status`, and `is_admin` (owner only)."""

    id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    is_admin = serializers.BooleanField(source="user.is_admin", required=False)
    is_owner = serializers.BooleanField(source="user.is_owner", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    reviewed_by = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)
    status = serializers.ChoiceField(choices=Profile.Status.choices, required=False)

    class Meta:
        model = Profile
        fields = [
            "id",
            "email",
            "display_name",
            "status",
            "is_admin",
            "is_owner",
            "created_at",
            "updated_at",
            "reviewed_by",
            "reviewed_at",
            "last_login",
        ]
        read_only_fields = ["created_at", "updated_at", "reviewed_at"]

    def validate(self, attrs):
        check_can_manage(self.context["request"].user, self.instance.user)
        if "user" in attrs and not self.context["request"].user.is_owner:
            raise PermissionDenied("Only the owner can grant or remove admin rights.")
        return attrs

    def update(self, instance, validated_data):
        actor = self.context["request"].user
        user = instance.user
        make_admin = validated_data.get("user", {}).get("is_admin")
        if make_admin is not None:
            user.is_staff = make_admin
            user.save(update_fields=["is_staff"])
            if make_admin and instance.status != Profile.Status.APPROVED:
                instance.set_status(Profile.Status.APPROVED, by=actor)
        if "status" in validated_data:
            instance.set_status(validated_data["status"], by=actor)
        return instance


def check_can_manage(actor: User, target: User) -> None:
    """Raise 403 unless `actor` may change or delete `target`."""
    if target.is_owner:
        raise PermissionDenied("The owner account cannot be rejected, changed or deleted.")
    if target.pk == actor.pk:
        raise PermissionDenied("You can't change or delete your own account here.")
    if target.is_staff and not actor.is_owner:
        raise PermissionDenied("Only the owner can change or delete another admin.")
