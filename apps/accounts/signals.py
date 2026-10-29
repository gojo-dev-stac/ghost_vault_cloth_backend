from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """Every user gets a profile. The owner (and createsuperuser accounts) start approved."""
    if not created:
        return
    # User.save() already made the owner staff + active.
    status = Profile.Status.APPROVED if instance.is_staff else Profile.Status.PENDING
    Profile.objects.get_or_create(user=instance, defaults={"status": status})


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def protect_owner(sender, instance, **kwargs):
    # Bulk/queryset deletes skip User.delete(); this signal still fires per object.
    if instance.is_owner:
        raise PermissionDenied("The owner account cannot be deleted.")
