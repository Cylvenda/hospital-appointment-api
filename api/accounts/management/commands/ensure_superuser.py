import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create or update the deploy-time superuser from environment variables."

    required_variables = (
        "DJANGO_SUPERUSER_EMAIL",
        "DJANGO_SUPERUSER_PASSWORD",
        "DJANGO_SUPERUSER_PHONE",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-if-unset",
            action="store_true",
            help="Exit successfully when none of the superuser variables are configured.",
        )

    def handle(self, *args, **options):
        values = {
            name: os.environ.get(name, "").strip()
            for name in self.required_variables
        }

        if options["skip_if_unset"] and not any(values.values()):
            self.stdout.write(
                self.style.WARNING(
                    "Superuser creation skipped: deploy-time variables are not set."
                )
            )
            return

        missing = [name for name, value in values.items() if not value]
        if missing:
            raise CommandError(
                "Missing required environment variable(s): " + ", ".join(missing)
            )

        User = get_user_model()
        email = User.objects.normalize_email(values["DJANGO_SUPERUSER_EMAIL"])

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            created = user is None

            if created:
                phone_owner = User.objects.filter(
                    phone=values["DJANGO_SUPERUSER_PHONE"]
                ).first()
                if phone_owner:
                    raise CommandError(
                        "DJANGO_SUPERUSER_PHONE is already assigned to another user."
                    )
                user = User(email=email)
            elif User.objects.filter(
                phone=values["DJANGO_SUPERUSER_PHONE"]
            ).exclude(pk=user.pk).exists():
                raise CommandError(
                    "DJANGO_SUPERUSER_PHONE is already assigned to another user."
                )

            user.phone = values["DJANGO_SUPERUSER_PHONE"]
            user.first_name = os.environ.get(
                "DJANGO_SUPERUSER_FIRST_NAME", user.first_name or ""
            ).strip()
            user.last_name = os.environ.get(
                "DJANGO_SUPERUSER_LAST_NAME", user.last_name or ""
            ).strip()
            user.role = User.Role.ADMIN
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.set_password(values["DJANGO_SUPERUSER_PASSWORD"])
            user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Superuser {email} {action}."))
