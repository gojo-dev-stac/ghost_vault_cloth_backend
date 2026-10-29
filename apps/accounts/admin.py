from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile, User

# Django's admin site lets in any active staff account; rejected accounts must not get in.
_site_has_permission = admin.site.has_permission
admin.site.has_permission = lambda request: _site_has_permission(request) and not request.user.is_rejected

OWNER_LOCKED_USER_FIELDS = ("email", "is_active", "is_staff", "is_superuser")


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = "user"
    readonly_fields = ("reviewed_by", "reviewed_at", "created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    ordering = ("-date_joined",)
    list_display = ("email", "display_name", "status", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_active", "profile__status")
    search_fields = ("email", "display_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2")}),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, *OWNER_LOCKED_USER_FIELDS) if obj and obj.is_owner else fields

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.is_owner) and super().has_delete_permission(request, obj)

    @admin.display(description="Status", ordering="profile__status")
    def status(self, obj):
        return getattr(getattr(obj, "profile", None), "status", "-")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "reviewed_by", "reviewed_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "user__display_name")
    readonly_fields = ("reviewed_by", "reviewed_at", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "status") if obj and obj.user.is_owner else fields

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.user.is_owner) and super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            obj.set_status(obj.status, by=request.user)
        else:
            super().save_model(request, obj, form, change)
