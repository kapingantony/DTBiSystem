from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from openpyxl import load_workbook

from staff.models import Startup

SHEET_NAME = 'STARTUPS'

# Cluster label -> (sn_col, org_col, desc_col) pairs: workbook uses a left and a right block.
BLOCKS = ((3, 4, 5), (7, 8, 9))

CLUSTERS = {
    'MANUFACTURERS',
    'EDUTECH',
    'TOURISM',
    'LOGISTIC',
    'REAL ESTATE/SERVICES',
    'CYBER SECURITY',
    'FINTECH/E-COMMERCE',
    'RENEWABLE ENERGY',
    'ENTERTAINMENT',
    'HEALTHY',
}

# Cluster -> industry value containing a STARTUP_INDUSTRY_CATEGORIES sector keyword.
INDUSTRY_MAP = {
    'MANUFACTURERS': 'Manufacturing',
    'EDUTECH': 'EdTech',
    'TOURISM': 'Tourism',
    'LOGISTIC': 'Transport & Logistics',
    'REAL ESTATE/SERVICES': 'Real Estate',
    'CYBER SECURITY': 'Cybersecurity',
    'FINTECH/E-COMMERCE': 'Fintech & E-commerce',
    'RENEWABLE ENERGY': 'Renewable Energy',
    'ENTERTAINMENT': 'Creative Industries & Media',
    'HEALTHY': 'Health & MedTech',
}


class Command(BaseCommand):
    help = 'Replace the startup directory with cluster organizations from a DTBi workbook.'

    def add_arguments(self, parser):
        parser.add_argument('workbook', nargs='?', default='modified.xlsx')
        parser.add_argument('--replace', action='store_true',
                            help='Delete all existing startups before inserting.')

    def handle(self, *args, **options):
        path = Path(options['workbook']).expanduser()
        if not path.exists():
            raise CommandError(f'Workbook does not exist: {path}')

        entries = self.parse(path)
        if not entries:
            raise CommandError('No organization rows found in the workbook.')

        if options['replace']:
            deleted, _ = Startup.objects.all().delete()
            self.stdout.write(f'Deleted {deleted} existing rows (startups + cascaded relations).')

        created = 0
        for entry in entries:
            _, was_created = Startup.objects.get_or_create(
                name=entry['name'],
                defaults={
                    'description': entry['description'],
                    'industry': INDUSTRY_MAP.get(entry['cluster'], ''),
                    'source': path.name,
                    'status': 'active',
                    'directory_visible': True,
                    'startup_type': 'public',
                },
            )
            created += int(was_created)

        visible = Startup.objects.filter(directory_visible=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Imported {created} organizations; directory now shows {visible} startups.'
        ))

    def parse(self, path: Path):
        workbook = load_workbook(path, read_only=True, data_only=True)
        if SHEET_NAME not in workbook.sheetnames:
            raise CommandError(f'Missing sheet {SHEET_NAME!r} in {path.name}.')
        rows = list(workbook[SHEET_NAME].iter_rows(values_only=True))

        entries = []
        seen = set()
        cluster = {block: None for block in BLOCKS}
        for row in rows:
            for block in BLOCKS:
                sn_i, org_i, desc_i = block
                sn = row[sn_i] if sn_i < len(row) else None
                org = row[org_i] if org_i < len(row) else None
                desc = row[desc_i] if desc_i < len(row) else None
                if isinstance(org, str) and org.strip().upper() in CLUSTERS and not isinstance(sn, (int, float)):
                    cluster[block] = org.strip().upper()
                    continue
                if isinstance(sn, str) and sn.strip().upper() in CLUSTERS and org is None:
                    cluster[block] = sn.strip().upper()
                    continue
                if not isinstance(sn, (int, float)) or not isinstance(org, str):
                    continue
                name = ' '.join(org.split())
                if not name or name.upper() == 'ORGANIZATION' or name in seen:
                    continue
                seen.add(name)
                entries.append({
                    'name': name,
                    'description': ' '.join(str(desc).split()) if desc else '',
                    'cluster': cluster[block],
                    'row': int(sn),
                })
        return entries
