from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Product

PASSWORD = "Sp3ctral-hoodie!"


class ProductApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@ghost.test", PASSWORD, is_staff=True)
        self.member = User.objects.create_user("member@ghost.test", PASSWORD)
        self.product = Product.objects.create(name="Phantom Skull", price=220)
        self.product.set_sizes({"S": 3, "M": 5, "L": 0, "XL": 2})

    def payload(self, **overrides):
        data = {
            "name": "Void Skull",
            "description": "Obsidian skull",
            "price": 280,
            "image_url": "https://cdn.example.com/void.jpg",
            "sizes": {"S": 4, "M": 6, "L": 8, "XL": 4},
            "category": "Hoodies",
        }
        data.update(overrides)
        return data

    def test_public_can_list_and_read(self):
        res = self.client.get("/api/products/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]["sizes"], {"S": 3, "M": 5, "L": 0, "XL": 2})
        self.assertEqual(res.data[0]["total_stock"], 10)
        self.assertEqual(res.data[0]["price"], 220)
        res = self.client.get(f"/api/products/{self.product.id}/")
        self.assertEqual(res.data["name"], "Phantom Skull")

    def test_non_admin_cannot_write(self):
        self.assertEqual(self.client.post("/api/products/", self.payload(), format="json").status_code, 401)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.post("/api/products/", self.payload(), format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/products/{self.product.id}/").status_code, 403)

    def test_admin_creates_updates_deletes(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post("/api/products/", self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["sizes"], {"S": 4, "M": 6, "L": 8, "XL": 4})
        pid = res.data["id"]

        res = self.client.patch(f"/api/products/{pid}/", {"price": 300, "sizes": {"M": 1}}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["price"], 300)
        self.assertEqual(res.data["sizes"], {"S": 4, "M": 1, "L": 8, "XL": 4})

        self.assertEqual(self.client.delete(f"/api/products/{pid}/").status_code, 204)
        self.assertFalse(Product.objects.filter(pk=pid).exists())

    def test_validation(self):
        self.client.force_authenticate(self.admin)
        for bad in (
            {"price": -1},
            {"sizes": {"XXL": 1}},
            {"sizes": {"S": -2}},
            {"sizes": {"S": 1.5}},
            {"image_url": "javascript:alert(1)"},
        ):
            res = self.client.post("/api/products/", self.payload(**bad), format="json")
            self.assertEqual(res.status_code, 400, bad)

    def test_blank_image_url_stored_as_null(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post("/api/products/", self.payload(image_url=""), format="json")
        self.assertIsNone(res.data["image_url"])

    def test_filters(self):
        Product.objects.create(name="Cap", price=40, category="Accessories")
        self.assertEqual(len(self.client.get("/api/products/?category=accessories").data), 1)
        self.assertEqual(len(self.client.get("/api/products/?search=phantom").data), 1)
        self.assertEqual(len(self.client.get("/api/products/?in_stock=1").data), 1)

    def test_seed_command_is_idempotent(self):
        call_command("seed_products", stdout=StringIO())
        call_command("seed_products", stdout=StringIO())
        self.assertEqual(Product.objects.count(), 6)


class LocalImageMigrationTests(APITestCase):
    def test_lovable_urls_map_to_local_files(self):
        from importlib import import_module

        local_url = import_module("apps.products.migrations.0002_local_product_images").local_url
        base = "/__l5e/assets-v1/c961cc0b-1bf8-4203-ac0e-0f34d1ecccb4"
        self.assertEqual(local_url(f"{base}/hoodie-004.jpeg"), "/products/hoodie-004.jpg")
        self.assertEqual(local_url(f"{base}/hoodie-001.webp"), "/products/hoodie-001.webp")
        self.assertIsNone(local_url("https://cdn.example.com/x.jpg"))

    def test_seed_images_exist_in_frontend(self):
        from pathlib import Path

        from django.conf import settings

        from .management.commands.seed_products import CATALOG

        public = Path(settings.BASE_DIR).parent / "frontend" / "public"
        for item in CATALOG:
            self.assertTrue((public / item["image_url"].lstrip("/")).is_file(), item["image_url"])
