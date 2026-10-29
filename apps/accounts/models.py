"""
Accounts: the user (email login), their profile and the vault approval workflow.

- `Profile.status` is pending / approved / rejected. Only approved accounts may
  use the vault; rejected accounts cannot sign in at all.
- `User.is_staff` marks an admin, but admin rights also require approved status.
- The owner (settings.GHOST_OWNER_EMAIL) is always active, approved and admin,
  and can never be rejected or deleted. Only the owner can grant or remove admin.
"""
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Admin role: can approve members, manage inventory, orders, reviews and support.",
    )
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.is_owner:
            # The owner can never be demoted or deactivated.
            self.is_staff = True
            self.is_active = True
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "is_staff", "is_active"}
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_owner:
            raise PermissionDenied("The owner account cannot be deleted.")
        return super().delete(*args, **kwargs)

    @property
    def is_owner(self) -> bool:
        return bool(self.email) and self.email.lower() == settings.GHOST_OWNER_EMAIL

    @property
    def status(self) -> str | None:
        profile = getattr(self, "profile", None)
        return profile.status if profile else None

    @property
    def is_approved(self) -> bool:
        return self.status == Profile.Status.APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.status == Profile.Status.REJECTED

    @property
    def is_admin(self) -> bool:
        """Admin rights need the admin flag AND an active, approved account."""
        return self.is_active and self.is_staff and self.is_approved

    @property
    def can_shop(self) -> bool:
        """Only active, approved accounts may enter the Vault and buy."""
        return self.is_active and self.is_approved


class Profile(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} ({self.status})"

    def save(self, *args, **kwargs):
        if self.user.is_owner:
            self.status = self.Status.APPROVED  # the owner is always approved
        super().save(*args, **kwargs)

    def set_status(self, status: str, by=None):
        if self.user.is_owner and status != self.Status.APPROVED:
            raise PermissionDenied("The owner account cannot be rejected.")
        self.status = status
        self.reviewed_by = by
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
