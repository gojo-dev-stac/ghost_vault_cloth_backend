from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import Profile, User
from apps.products.models import Product

PASSWORD = "Sp3ctral-hoodie!"


class ReviewApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@ghost.test", PASSWORD, is_staff=True)
        self.member = User.objects.create_user("wraith@ghost.test", PASSWORD, display_name="Wraith")
        self.member.profile.set_status(Profile.Status.APPROVED)
        self.nameless = User.objects.create_user("shade@ghost.test", PASSWORD)
        self.nameless.profile.set_status(Profile.Status.APPROVED)
        self.pending = User.objects.create_user("pending@ghost.test", PASSWORD)
        self.skull = Product.objects.create(name="Phantom Skull", price=220)
        self.flame = Product.objects.create(name="Blue Flame", price=260)

    def post(self, product=None, rating=5, comment="Heavy fleece, insane print.", **extra):
        product = product or self.skull
        data = {"product_id": str(product.id), "rating": rating, "comment": comment, **extra}
        return self.client.post("/api/reviews/", data, format="json")

    def test_member_posts_review_with_server_side_author(self):
        self.client.force_authenticate(self.member)
        res = self.post(author_name="Admin", admin_reply="fake reply")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["author_name"], "Wraith")
        self.assertIsNone(res.data["admin_reply"])
        self.assertTrue(res.data["is_mine"])

    def test_author_falls_back_to_email_name(self):
        self.client.force_authenticate(self.nameless)
        self.assertEqual(self.post().data["author_name"], "shade")

    def test_pending_and_anonymous_cannot_post(self):
        self.assertEqual(self.post().status_code, 401)
        self.client.force_authenticate(self.pending)
        self.assertEqual(self.post().status_code, 403)

    def test_validation(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.post(rating=0).status_code, 400)
        self.assertEqual(self.post(rating=6).status_code, 400)
        self.assertEqual(self.post(comment="   ").status_code, 400)
        self.assertEqual(self.post(comment="x" * 2001).status_code, 400)
        bad = {"product_id": "00000000-0000-0000-0000-000000000000", "rating": 5, "comment": "hi"}
        self.assertEqual(self.client.post("/api/reviews/", bad, format="json").status_code, 400)

    def test_public_list_filtered_by_product(self):
        self.client.force_authenticate(self.member)
        self.post()
        self.post(product=self.flame, rating=3)
        self.client.force_authenticate(None)
        res = self.client.get(f"/api/reviews/?product={self.skull.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertFalse(res.data[0]["is_mine"])
        self.assertEqual(len(self.client.get("/api/reviews/").data), 2)
        self.assertEqual(self.client.get("/api/reviews/?product=not-a-uuid").data, [])

    def test_admin_reply_and_clear(self):
        self.client.force_authenticate(self.member)
        rid = self.post().data["id"]
        url = f"/api/reviews/{rid}/reply/"
        self.assertEqual(self.client.patch(url, {"reply": "hi"}, format="json").status_code, 403)

        self.client.force_authenticate(self.admin)
        res = self.client.patch(url, {"reply": "  Thank you, Wraith.  "}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["admin_reply"], "Thank you, Wraith.")
        self.assertIsNotNone(res.data["replied_at"])
        self.assertEqual(len(self.client.get("/api/reviews/?unreplied=1").data), 0)

        res = self.client.patch(url, {"reply": ""}, format="json")
        self.assertIsNone(res.data["admin_reply"])
        self.assertIsNone(res.data["replied_at"])

    def test_only_admin_deletes(self):
        self.client.force_authenticate(self.member)
        rid = self.post().data["id"]
        self.assertEqual(self.client.delete(f"/api/reviews/{rid}/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/api/reviews/{rid}/").status_code, 204)

    def test_reviews_removed_with_product(self):
        self.client.force_authenticate(self.member)
        self.post()
        self.skull.delete()
        self.assertEqual(self.client.get("/api/reviews/").data, [])
