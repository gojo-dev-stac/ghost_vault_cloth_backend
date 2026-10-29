"""Point product images that used Lovable-hosted URLs at the copies in frontend/public/products/."""
import re

from django.db import migrations

LOVABLE_IMAGE = re.compile(r"^/__l5e/assets-v1/[0-9a-f-]+/(hoodie-00[1-5])\.(webp|jpe?g)$")


def local_url(url):
    match = LOVABLE_IMAGE.match(url or "")
    if not match:
        return None
    name, ext = match.groups()
    return f"/products/{name}.{'jpg' if ext == 'jpeg' else ext}"


def forwards(apps, schema_editor):
    for model in (apps.get_model("products", "Product"), apps.get_model("orders", "OrderItem")):
        for obj in model.objects.filter(image_url__startswith="/__l5e/"):
            new = local_url(obj.image_url)
            if new:
                obj.image_url = new
                obj.save(update_fields=["image_url"])


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
        ("orders", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
