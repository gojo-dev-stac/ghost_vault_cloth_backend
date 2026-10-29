"""
JWT authentication that enforces the access workflow on every request.

Rejected (or deactivated) accounts cannot sign in or refresh tokens, and a token
issued before a rejection stops working on its next request. The 401 body
carries {"code": "account_rejected"} so the frontend can show the REJECTED screen.
"""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

REJECTED_MESSAGE = "Your access request was rejected. Contact GHOST if you believe this is a mistake."


def rejected_error() -> AuthenticationFailed:
    return AuthenticationFailed({"detail": REJECTED_MESSAGE, "code": "account_rejected"})


def user_can_authenticate(user) -> bool:
    """SIMPLE_JWT USER_AUTHENTICATION_RULE: used for login and token refresh."""
    return user is not None and user.is_active and not user.is_rejected


class GhostJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.is_rejected:
            raise rejected_error()
        return user
