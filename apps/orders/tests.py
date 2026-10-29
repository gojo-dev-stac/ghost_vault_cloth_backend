from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import Profile, User
from apps.products.models import Product

PASSWORD = "Sp3ctral-hoodie!"


class OrderApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@ghost.test", PASSWORD, is_staff=True)
        self.member = User.objects.create_user("member@ghost.test", PASSWORD, display_name="Phantom")
        self.member.profile.set_status(Profile.Status.APPROVED)
        self.pending = User.objects.create_user("pending@ghost.test", PASSWORD)
        self.skull = Product.objects.create(name="Phantom Skull", price=220, image_url="/img/1.webp")
        self.skull.set_sizes({"S": 3, "M": 5, "L": 0, "XL": 2})
        self.flame = Product.objects.create(name="Blue Flame", price=260)
        self.flame.set_sizes({"S": 1, "M": 3, "L": 5, "XL": 1})

    def order(self, items, payment="COD", **customer):
        return self.client.post(
            "/api/orders/",
            {"items": items, "payment_method": payment, "customer": {"firstName": "Ghost", "city": "Lahore", **customer}},
            format="json",
        )

    def line(self, product, size, quantity=1, **extra):
        return {"product_id": str(product.id), "size": size, "quantity": quantity, **extra}

    def stock(self, product):
        return Product.objects.get(pk=product.pk).sizes

    def test_place_order_prices_from_db_and_decrements_stock(self):
        self.client.force_authenticate(self.member)
        res = self.order([self.line(self.skull, "M", 2, price=1), self.line(self.flame, "L", 1)], name="G. Host")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertRegex(res.data["order_id"], r"^GV-[0-9A-F]{8}$")
        self.assertEqual(res.data["total"], 220 * 2 + 260)
        self.assertEqual(res.data["status"], "Pending")
        self.assertEqual(res.data["customer_email"], "member@ghost.test")
        self.assertEqual(res.data["customer_name"], "G. Host")
        self.assertEqual(res.data["items"][0]["price"], 220)
        self.assertEqual(res.data["items"][0]["image_url"], "/img/1.webp")
        self.assertEqual(self.stock(self.skull)["M"], 3)
        self.assertEqual(self.stock(self.flame)["L"], 4)

    def test_oversell_rolls_back_whole_order(self):
        self.client.force_authenticate(self.member)
        res = self.order([self.line(self.skull, "M", 1), self.line(self.flame, "S", 2)])
        self.assertEqual(res.status_code, 400)
        self.assertIn("has only 1 left", str(res.data))
        self.assertEqual(self.stock(self.skull)["M"], 5)  # first line rolled back
        self.assertFalse(self.member.orders.exists())

    def test_duplicate_lines_are_combined_for_stock_check(self):
        self.client.force_authenticate(self.member)
        res = self.order([self.line(self.flame, "S", 1), self.line(self.flame, "S", 1)])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.stock(self.flame)["S"], 1)

    def test_out_of_stock_size(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.order([self.line(self.skull, "L")]).status_code, 400)

    def test_invalid_input(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.order([]).status_code, 400)
        self.assertEqual(self.order([self.line(self.skull, "XXL")]).status_code, 400)
        self.assertEqual(self.order([self.line(self.skull, "M", 0)]).status_code, 400)
        self.assertEqual(self.order([self.line(self.skull, "M")], payment="Bitcoin").status_code, 400)
        bogus = {"product_id": "00000000-0000-0000-0000-000000000000", "size": "M", "quantity": 1}
        self.assertEqual(self.order([bogus]).status_code, 400)

    def test_pending_and_anonymous_cannot_order(self):
        self.assertEqual(self.order([self.line(self.skull, "M")]).status_code, 401)
        self.client.force_authenticate(self.pending)
        self.assertEqual(self.order([self.line(self.skull, "M")]).status_code, 403)
        self.assertEqual(self.stock(self.skull)["M"], 5)

    def test_admin_can_order(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.order([self.line(self.skull, "S")]).status_code, 201)

    def test_members_see_only_their_orders(self):
        self.client.force_authenticate(self.member)
        mine = self.order([self.line(self.skull, "S")]).data["id"]
        self.client.force_authenticate(self.admin)
        theirs = self.order([self.line(self.skull, "S")]).data["id"]

        self.assertEqual({o["id"] for o in self.client.get("/api/orders/").data}, {mine, theirs})
        self.assertEqual([o["id"] for o in self.client.get("/api/orders/?mine=1").data], [theirs])

        self.client.force_authenticate(self.member)
        self.assertEqual([o["id"] for o in self.client.get("/api/orders/").data], [mine])
        self.assertEqual(self.client.get(f"/api/orders/{theirs}/").status_code, 404)

    def test_admin_updates_status(self):
        self.client.force_authenticate(self.member)
        oid = self.order([self.line(self.skull, "S")]).data["id"]
        url = f"/api/orders/{oid}/status/"
        self.assertEqual(self.client.patch(url, {"status": "Shipped"}, format="json").status_code, 403)

        self.client.force_authenticate(self.admin)
        for status in ("Confirmed", "Processing", "Shipped", "Delivered"):
            res = self.client.patch(url, {"status": status}, format="json")
            self.assertEqual(res.status_code, 200, res.data)
            self.assertEqual(res.data["status"], status)
        self.assertEqual(self.client.patch(url, {"status": "Lost"}, format="json").status_code, 400)
        self.assertEqual(len(self.client.get("/api/orders/?status=Delivered").data), 1)

    def test_deleting_product_keeps_order_history(self):
        self.client.force_authenticate(self.member)
        oid = self.order([self.line(self.skull, "S")]).data["id"]
        self.skull.delete()
        item = self.client.get(f"/api/orders/{oid}/").data["items"][0]
        self.assertIsNone(item["product_id"])
        self.assertEqual(item["name"], "Phantom Skull")
