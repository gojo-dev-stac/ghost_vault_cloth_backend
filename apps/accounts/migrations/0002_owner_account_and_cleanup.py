"""
One-off data fixes for existing databases:

- If the owner account (hasshamahmed73@gmail.com) exists, make sure it is
  active, admin and approved.
- Delete the account 12hashamahmed@gmail.com if it exists (requested removal).
  Its orders, reviews and messages stay, unlinked from the account.
"""
from django.db import migrations

OWNER_EMAIL = "hasshamahmed73@gmail.com"
REMOVED_EMAILS = ["12hashamahmed@gmail.com"]


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Profile = apps.get_model("accounts", "Profile")

    owner = User.objects.filter(email__iexact=OWNER_EMAIL).first()
    if owner:
        User.objects.filter(pk=owner.pk).update(is_staff=True, is_active=True)
        Profile.objects.update_or_create(user=owner, defaults={"status": "approved"})

    for email in REMOVED_EMAILS:
        User.objects.filter(email__iexact=email).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        # Deleting a user updates rows in these apps (SET_NULL / CASCADE).
        ("orders", "0001_initial"),
        ("reviews", "0001_initial"),
        ("contact", "0001_initial"),
        ("token_blacklist", "0013_alter_blacklistedtoken_options_and_more"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
