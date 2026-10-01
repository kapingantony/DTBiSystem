from django.core.management.base import BaseCommand
from django.db import transaction

from staff.models import Startup
from staff.startup_catalog import STARTUP_CATALOG


class Command(BaseCommand):
    help = "Replace published directory listings with the organization catalog from modified.xlsx."

    @transaction.atomic
    def handle(self, *args, **options):
        # Keep old records and their linked operational history, but remove them from
        # the public directory before publishing this source catalog.
        retired_count = Startup.objects.filter(directory_visible=True).update(directory_visible=False)
        source = "Startup catalog · modified.xlsx"
        created_count = 0
        updated_count = 0
        seen = set()

        for category, name, description in STARTUP_CATALOG:
            normalized_name = " ".join(name.casefold().split())
            if normalized_name in seen:
                continue
            seen.add(normalized_name)
            startup = Startup.objects.filter(name__iexact=name).order_by("pk").first()
            if startup is None:
                startup = Startup(name=name)
                created_count += 1
            else:
                updated_count += 1
            startup.startup_type = "public"
            startup.description = description
            startup.industry = category
            startup.source = source
            startup.directory_visible = True
            startup.status = "active"
            startup.save()

        self.stdout.write(self.style.SUCCESS(
            f"Published {len(seen)} organization profiles across {len({row[0] for row in STARTUP_CATALOG})} categories; "
            f"created {created_count}, updated {updated_count}, and retired {retired_count} previous listings."
        ))
