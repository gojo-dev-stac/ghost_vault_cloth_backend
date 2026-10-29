"""Reusable DRF permissions for the access workflow (used by every app)."""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Approved admins only (User.is_staff + approved status)."""

    message = "Admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)


class IsApprovedMember(BasePermission):
    """Approved accounts only: may enter the Vault, order and review."""

    message = "Your vault access has not been approved yet."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.can_shop)


class IsAdminOrReadOnly(BasePermission):
    """Anyone may read; only admins may write."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)
