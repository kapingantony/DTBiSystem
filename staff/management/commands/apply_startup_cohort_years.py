from django.core.management.base import BaseCommand
from django.db import transaction

from staff.models import Startup
from staff.startup_catalog import STARTUP_COHORT_YEAR_UPDATES


class Command(BaseCommand):
    help = 'Apply programme-supplied cohort years to existing published startup profiles.'

    @transaction.atomic
    def handle(self, *args, **options):
        updated = []
        missing = []
        for name, cohort_year in STARTUP_COHORT_YEAR_UPDATES:
            startup = Startup.objects.filter(name__iexact=name, directory_visible=True).order_by('pk').first()
            if startup is None:
                missing.append(name)
                continue
            startup.year_incubated = cohort_year
            startup.save(update_fields=['year_incubated', 'updated_at'])
            updated.append((startup.name, cohort_year))

        for name, cohort_year in updated:
            self.stdout.write(f'Updated {name}: cohort {cohort_year}')
        for name in missing:
            self.stdout.write(self.style.WARNING(f'No published startup match: {name}'))
        self.stdout.write(self.style.SUCCESS(f'Applied {len(updated)} supplied cohort years; {len(missing)} listed names need a directory match.'))
