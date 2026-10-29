import re

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Profile, User

PASSWORD = "Sp3ctral-hoodie!"


@override_settings(GHOST_OWNER_EMAIL="boss@ghost.test")
class AuthFlowTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset auth throttle counters between tests

    def register(self, email="member@ghost.test", name="Phantom"):
        return self.client.post(
            "/api/auth/register/", {"email": email, "password": PASSWORD, "display_name": name}, format="json"
        )

    def login(self, email, password=PASSWORD):
        return self.client.post("/api/auth/login/", {"email": email, "password": password}, format="json")

    def auth(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_register_starts_pending_and_returns_tokens(self):
        res = self.register()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["user"]["status"], "pending")
        self.assertFalse(res.data["user"]["is_admin"])
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_duplicate_email_rejected_case_insensitively(self):
        self.register()
        res = self.register(email="MEMBER@ghost.test")
        self.assertEqual(res.status_code, 400)

    def test_weak_password_rejected(self):
        res = self.client.post("/api/auth/register/", {"email": "a@ghost.test", "password": "123"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_admin_email_auto_approved_as_admin(self):
        res = self.register(email="Boss@ghost.test")
        self.assertEqual(res.data["user"]["status"], "approved")
        self.assertTrue(res.data["user"]["is_admin"])

    def test_login_and_me(self):
        self.register()
        res = self.login("Member@Ghost.test")
        self.assertEqual(res.status_code, 200, res.data)
        self.auth(res.data["access"])
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.data["email"], "member@ghost.test")
        self.assertEqual(me.data["display_name"], "Phantom")

    def test_bad_password_fails(self):
        self.register()
        self.assertEqual(self.login("member@ghost.test", "wrong").status_code, 401)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_member_cannot_change_own_status(self):
        access = self.register().data["access"]
        self.auth(access)
        res = self.client.patch("/api/auth/me/", {"status": "approved", "display_name": "Wraith"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["display_name"], "Wraith")
        self.assertEqual(res.data["status"], "pending")

    def test_member_cannot_use_admin_endpoints(self):
        self.auth(self.register().data["access"])
        self.assertEqual(self.client.get("/api/auth/members/").status_code, 403)

    def test_admin_approves_member(self):
        member_id = self.register().data["user"]["id"]
        self.auth(self.register(email="boss@ghost.test").data["access"])

        pending = self.client.get("/api/auth/members/?status=pending")
        self.assertEqual([m["id"] for m in pending.data], [member_id])

        res = self.client.patch(f"/api/auth/members/{member_id}/", {"status": "approved"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "approved")
        self.assertEqual(res.data["reviewed_by"], "boss@ghost.test")
        self.assertTrue(User.objects.get(pk=member_id).can_shop)

        res = self.client.patch(f"/api/auth/members/{member_id}/", {"status": "bogus"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_refresh_rotates_and_logout_blacklists(self):
        refresh = self.register().data["refresh"]
        res = self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(res.status_code, 200)
        new_refresh = res.data["refresh"]
        # the rotated-out token is blacklisted
        self.assertEqual(
            self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json").status_code, 401
        )
        self.assertEqual(self.client.post("/api/auth/logout/", {"refresh": new_refresh}, format="json").status_code, 205)
        self.assertEqual(
            self.client.post("/api/auth/token/refresh/", {"refresh": new_refresh}, format="json").status_code, 401
        )

    def test_password_reset_flow(self):
        self.register()
        res = self.client.post("/api/auth/password/reset/", {"email": "member@ghost.test"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        uid, token = re.search(r"uid=([\w-]+)&token=([\w-]+)", mail.outbox[0].body).groups()

        bad = self.client.post(
            "/api/auth/password/reset/confirm/",
            {"uid": uid, "token": "nope", "new_password": "N3w-vault-pass!"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

        ok = self.client.post(
            "/api/auth/password/reset/confirm/",
            {"uid": uid, "token": token, "new_password": "N3w-vault-pass!"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(self.login("member@ghost.test", "N3w-vault-pass!").status_code, 200)

    def test_password_reset_unknown_email_is_silent(self):
        res = self.client.post("/api/auth/password/reset/", {"email": "ghost@nowhere.test"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_change_requires_current_password(self):
        self.auth(self.register().data["access"])
        bad = self.client.post(
            "/api/auth/password/change/",
            {"current_password": "wrong", "new_password": "N3w-vault-pass!"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post(
            "/api/auth/password/change/",
            {"current_password": PASSWORD, "new_password": "N3w-vault-pass!"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200)

    def test_createsuperuser_gets_approved_profile(self):
        admin = User.objects.create_superuser("root@ghost.test", PASSWORD)
        self.assertEqual(admin.profile.status, Profile.Status.APPROVED)
        self.assertTrue(admin.can_shop)


class CorsTests(APITestCase):
    def preflight(self, origin):
        return self.client.options(
            "/api/auth/login/",
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )

    def test_local_frontend_origins_allowed(self):
        for origin in ("http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://localhost:8080"):
            res = self.preflight(origin)
            self.assertEqual(res.headers.get("access-control-allow-origin"), origin, origin)
            self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")
            self.assertIn("authorization", res.headers.get("access-control-allow-headers", ""))

    def test_unknown_origin_rejected(self):
        self.assertNotIn("access-control-allow-origin", self.preflight("https://evil.example.com").headers)

    def test_error_responses_carry_cors_headers(self):
        # A 401 must still be readable by the browser, or it shows up as a network error.
        res = self.client.get("/api/auth/me/", HTTP_ORIGIN="http://localhost:3000")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")


@override_settings(GHOST_OWNER_EMAIL="owner@ghost.test")
class AccessRulesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("owner@ghost.test", PASSWORD)
        self.admin = User.objects.create_user("admin@ghost.test", PASSWORD, is_staff=True)
        self.member = User.objects.create_user("member@ghost.test", PASSWORD)
        self.member.profile.set_status(Profile.Status.APPROVED)
        self.pending = User.objects.create_user("pending@ghost.test", PASSWORD)

    def login(self, email):
        return self.client.post("/api/auth/login/", {"email": email, "password": PASSWORD}, format="json")

    def as_user(self, user):
        self.client.force_authenticate(user)

    def reject(self, user):
        user.profile.set_status(Profile.Status.REJECTED)
        user.refresh_from_db()

    # --- rejected accounts ------------------------------------------------

    def test_rejected_user_cannot_log_in(self):
        self.reject(self.member)
        res = self.login("member@ghost.test")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["code"], "account_rejected")
        self.assertIn("rejected", str(res.data["detail"]))
        self.assertNotIn("access", res.data)

    def test_wrong_password_for_rejected_user_does_not_reveal_status(self):
        self.reject(self.member)
        res = self.client.post("/api/auth/login/", {"email": "member@ghost.test", "password": "nope"}, format="json")
        self.assertEqual(res.status_code, 401)
        self.assertNotEqual(res.data.get("code"), "account_rejected")

    def test_existing_tokens_stop_working_after_rejection(self):
        tokens = self.login("member@ghost.test").data
        self.reject(self.member)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["code"], "account_rejected")
        self.client.credentials()
        res = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["code"], "account_rejected")

    def test_rejected_admin_loses_admin_access(self):
        tokens = self.login("admin@ghost.test").data
        self.reject(self.admin)
        self.assertFalse(self.admin.is_admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get("/api/auth/members/").status_code, 401)
        self.assertEqual(self.login("admin@ghost.test").status_code, 401)

    def test_rejected_staff_cannot_use_django_admin_site(self):
        self.reject(self.admin)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/admin/").status_code, 302)  # bounced to the admin login

    def test_refresh_for_deleted_account_is_401_not_500(self):
        tokens = self.login("member@ghost.test").data
        self.member.delete()
        res = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 401)

    # --- pending accounts -------------------------------------------------

    def test_pending_user_logs_in_but_only_sees_status(self):
        res = self.login("pending@ghost.test")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["status"], "pending")
        self.assertFalse(self.pending.can_shop)

    def test_staff_flag_without_approval_is_not_admin(self):
        self.admin.profile.set_status(Profile.Status.PENDING)
        self.admin.refresh_from_db()
        self.as_user(self.admin)
        self.assertEqual(self.client.get("/api/auth/members/").status_code, 403)

    # --- the owner ----------------------------------------------------------

    def test_owner_is_always_approved_admin(self):
        self.assertTrue(self.owner.is_owner)
        self.assertTrue(self.owner.is_admin)
        self.assertEqual(self.owner.profile.status, Profile.Status.APPROVED)
        self.owner.is_staff = False
        self.owner.is_active = False
        self.owner.save()
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_staff and self.owner.is_active)
        self.owner.profile.status = Profile.Status.REJECTED
        self.owner.profile.save()
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.status, Profile.Status.APPROVED)

    def test_owner_cannot_be_rejected_or_deleted_by_admins(self):
        self.as_user(self.admin)
        url = f"/api/auth/members/{self.owner.id}/"
        self.assertEqual(self.client.patch(url, {"status": "rejected"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.profile.status, Profile.Status.APPROVED)

    def test_owner_cannot_be_deleted_at_model_level(self):
        from django.core.exceptions import PermissionDenied
        from django.db import transaction

        with self.assertRaises(PermissionDenied), transaction.atomic():
            self.owner.delete()
        with self.assertRaises(PermissionDenied), transaction.atomic():
            User.objects.filter(pk=self.owner.pk).delete()
        with self.assertRaises(PermissionDenied):
            self.owner.profile.set_status(Profile.Status.REJECTED)
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())

    def test_owner_signup_via_api_is_owner_admin(self):
        User.objects.filter(pk=self.owner.pk).update(email="old-owner@ghost.test")
        res = self.client.post(
            "/api/auth/register/", {"email": "Owner@Ghost.test", "password": PASSWORD}, format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["user"]["status"], "approved")
        self.assertTrue(res.data["user"]["is_admin"])
        self.assertTrue(res.data["user"]["is_owner"])

    # --- managing admins / members -------------------------------------------

    def test_only_owner_grants_and_removes_admin(self):
        url = f"/api/auth/members/{self.member.id}/"
        self.as_user(self.admin)
        self.assertEqual(self.client.patch(url, {"is_admin": True}, format="json").status_code, 403)

        self.as_user(self.owner)
        res = self.client.patch(url, {"is_admin": True}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data["is_admin"])
        res = self.client.patch(url, {"is_admin": False}, format="json")
        self.assertFalse(res.data["is_admin"])

    def test_promoting_a_pending_member_approves_them(self):
        self.as_user(self.owner)
        res = self.client.patch(f"/api/auth/members/{self.pending.id}/", {"is_admin": True}, format="json")
        self.assertEqual(res.data["status"], "approved")
        self.assertTrue(res.data["is_admin"])

    def test_admins_cannot_manage_other_admins_or_themselves(self):
        other_admin = User.objects.create_user("admin2@ghost.test", PASSWORD, is_staff=True)
        self.as_user(self.admin)
        self.assertEqual(
            self.client.patch(f"/api/auth/members/{other_admin.id}/", {"status": "rejected"}, format="json").status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(f"/api/auth/members/{self.admin.id}/", {"status": "rejected"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client.delete(f"/api/auth/members/{other_admin.id}/").status_code, 403)
        # the owner can
        self.as_user(self.owner)
        res = self.client.patch(f"/api/auth/members/{other_admin.id}/", {"status": "rejected"}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_admin_rejects_and_deletes_members(self):
        self.as_user(self.admin)
        url = f"/api/auth/members/{self.member.id}/"
        self.assertEqual(self.client.patch(url, {"status": "rejected"}, format="json").data["status"], "rejected")
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(User.objects.filter(email="member@ghost.test").exists())

    def test_list_marks_the_owner(self):
        self.as_user(self.admin)
        rows = {r["email"]: r for r in self.client.get("/api/auth/members/").data}
        self.assertTrue(rows["owner@ghost.test"]["is_owner"])
        self.assertFalse(rows["member@ghost.test"]["is_owner"])


class OwnerCleanupMigrationTests(APITestCase):
    def test_migration_fixes_owner_and_removes_requested_account(self):
        from importlib import import_module

        from django.apps import apps as global_apps

        from apps.orders.models import Order

        migration = import_module("apps.accounts.migrations.0002_owner_account_and_cleanup")
        with override_settings(GHOST_OWNER_EMAIL="someone-else@ghost.test"):
            owner = User.objects.create_user("hasshamahmed73@gmail.com", PASSWORD)
            owner.profile.set_status(Profile.Status.REJECTED)
            doomed = User.objects.create_user("12hashamahmed@gmail.com", PASSWORD)
            order = Order.objects.create(user=doomed, customer_email=doomed.email, total=10, payment_method="COD")

        migration.forwards(global_apps, None)

        owner.refresh_from_db()
        self.assertTrue(owner.is_staff and owner.is_active)
        self.assertEqual(owner.profile.status, Profile.Status.APPROVED)
        self.assertFalse(User.objects.filter(email="12hashamahmed@gmail.com").exists())
        order.refresh_from_db()
        self.assertIsNone(order.user)  # order history kept
