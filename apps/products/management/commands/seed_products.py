from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import Product

# The original GHOST catalog. Images are served by the frontend from
# frontend/public/products/.
CATALOG = [
    {
        "name": "GHOST Hoodie 001 — Phantom Skull",
        "description": "Heavyweight black hoodie with a screaming phantom skull wrapped in spectral blue spirits across the back and sleeves.",
        "price": 220,
        "image_url": "/products/hoodie-001.webp",
        "sizes": {"S": 3, "M": 5, "L": 8, "XL": 2},
    },
    {
        "name": "GHOST Hoodie 002 — Trinity Skull",
        "description": "Three skulls bound in barbed wire, lit by cold blue flame. Brushed fleece interior, contrast drawcords.",
        "price": 240,
        "image_url": "/products/hoodie-002.jpg",
        "sizes": {"S": 2, "M": 4, "L": 6, "XL": 3},
    },
    {
        "name": "GHOST Hoodie 003 — Blue Flame",
        "description": "Midnight navy hoodie engulfed in an electric blue flame skull with ember sparks. All-over print.",
        "price": 260,
        "image_url": "/products/hoodie-003.jpg",
        "sizes": {"S": 1, "M": 3, "L": 5, "XL": 1},
    },
    {
        "name": "GHOST Hoodie 004 — Void Skull",
        "description": "A cracked obsidian skull with glowing void-blue eyes, set against fractured lightning. All-over print.",
        "price": 280,
        "image_url": "/products/hoodie-004.jpg",
        "sizes": {"S": 4, "M": 6, "L": 8, "XL": 4},
    },
    {
        "name": "GHOST Hoodie 005 — Ghost Spirits",
        "description": "A procession of wraiths rising through mist, with spectral skulls down both sleeves. Heavyweight black fleece.",
        "price": 230,
        "image_url": "/products/hoodie-005.webp",
        "sizes": {"S": 4, "M": 6, "L": 10, "XL": 5},
    },
]


class Command(BaseCommand):
    help = "Add the original GHOST hoodie catalog (skips products whose name already exists)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for item in CATALOG:
            data = dict(item)
            sizes = data.pop("sizes")
            product, was_created = Product.objects.get_or_create(name=data["name"], defaults=data)
            if was_created:
                product.set_sizes(sizes)
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} product(s); {len(CATALOG) - created} already existed."))
