from django.contrib import admin
from django.utils import timezone

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "name", "email", "message")
    readonly_fields = ("user", "name", "email", "subject", "message", "replied_at", "created_at", "updated_at")
    fields = ("status", "user", "name", "email", "subject", "message", "admin_reply", "replied_at", "created_at")

    def save_model(self, request, obj, form, change):
        if "admin_reply" in form.changed_data and (obj.admin_reply or "").strip():
            obj.replied_at = timezone.now()
            if obj.status == Complaint.Status.OPEN:
                obj.status = Complaint.Status.REPLIED
        super().save_model(request, obj, form, change)
