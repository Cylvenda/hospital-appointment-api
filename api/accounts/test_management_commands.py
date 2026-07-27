from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class EnsureSuperuserCommandTests(TestCase):
    env = {
        "DJANGO_SUPERUSER_EMAIL": "admin@example.com",
        "DJANGO_SUPERUSER_PASSWORD": "A-secure-deploy-password",
        "DJANGO_SUPERUSER_PHONE": "+255700000001",
        "DJANGO_SUPERUSER_FIRST_NAME": "Deploy",
        "DJANGO_SUPERUSER_LAST_NAME": "Admin",
    }

    @patch.dict("os.environ", env, clear=False)
    def test_command_is_idempotent_and_updates_credentials(self):
        call_command("ensure_superuser", stdout=StringIO())

        User = get_user_model()
        user = User.objects.get(email=self.env["DJANGO_SUPERUSER_EMAIL"])
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.check_password(self.env["DJANGO_SUPERUSER_PASSWORD"]))

        with patch.dict(
            "os.environ",
            {
                **self.env,
                "DJANGO_SUPERUSER_PASSWORD": "A-new-secure-password",
            },
            clear=False,
        ):
            call_command("ensure_superuser", stdout=StringIO())

        self.assertEqual(User.objects.filter(email=user.email).count(), 1)
        user.refresh_from_db()
        self.assertTrue(user.check_password("A-new-secure-password"))
