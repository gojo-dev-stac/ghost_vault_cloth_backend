from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Complaint

PASSWORD = "Sp3ctral-hoodie!"
MESSAGE = {"name": "Ghost", "email": "visitor@ghost.test", "subject": "Wrong size", "message": "Got M, ordered L."}


class ContactApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@ghost.test", PASSWORD, is_staff=True)
        self.member = User.objects.create_user("member@ghost.test", PASSWORD)

    def send(self, **overrides):
        return self.client.post("/api/contact/", {**MESSAGE, **overrides}, format="json")

    def test_anonymous_can_send(self):
        res = self.send(status="Replied", admin_reply="sneaky")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["status"], "Open")
        self.assertIsNone(res.data["admin_reply"])
        self.assertIsNone(Complaint.objects.get().user)

    def test_signed_in_message_is_linked_and_visible_to_sender_only(self):
        self.client.force_authenticate(self.member)
        cid = self.send().data["id"]
        self.assertEqual(Complaint.objects.get().user, self.member)
        self.assertEqual([c["id"] for c in self.client.get("/api/contact/").data], [cid])

        other = User.objects.create_user("other@ghost.test", PASSWORD)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/contact/").data, [])
        self.assertEqual(self.client.get(f"/api/contact/{cid}/").status_code, 404)

    def test_anonymous_cannot_read_inbox(self):
        self.send()
        self.assertEqual(self.client.get("/api/contact/").status_code, 401)

    def test_validation(self):
        self.assertEqual(self.send(name="  ").status_code, 400)
        self.assertEqual(self.send(email="not-an-email").status_code, 400)
        self.assertEqual(self.send(subject="x" * 201).status_code, 400)
        self.assertEqual(self.send(message="x" * 5001).status_code, 400)

    def test_admin_inbox_reply_and_close(self):
        cid = self.send().data["id"]
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.patch(f"/api/contact/{cid}/reply/", {"reply": "x"}, format="json").status_code, 403)

        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get("/api/contact/?status=Open").data), 1)
        res = self.client.patch(f"/api/contact/{cid}/reply/", {"reply": "Swap on its way."}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "Replied")
        self.assertEqual(res.data["admin_reply"], "Swap on its way.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["visitor@ghost.test"])
        self.assertIn("Swap on its way.", mail.outbox[0].body)

        self.assertEqual(self.client.patch(f"/api/contact/{cid}/reply/", {"reply": ""}, format="json").status_code, 400)
        res = self.client.patch(f"/api/contact/{cid}/status/", {"status": "Closed"}, format="json")
        self.assertEqual(res.data["status"], "Closed")
        self.assertEqual(self.client.patch(f"/api/contact/{cid}/status/", {"status": "Nope"}, format="json").status_code, 400)

    def test_reply_without_email(self):
        cid = self.send().data["id"]
        self.client.force_authenticate(self.admin)
        self.client.patch(f"/api/contact/{cid}/reply/", {"reply": "Noted.", "send_email": False}, format="json")
        self.assertEqual(len(mail.outbox), 0)

    def test_send_is_rate_limited(self):
        codes = [self.send().status_code for _ in range(6)]
        self.assertEqual(codes[:5], [201] * 5)
        self.assertEqual(codes[5], 429)
