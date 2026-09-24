from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from openpyxl import load_workbook

from staff.models import Investor, Mentor, Startup


class Command(BaseCommand):
    help = 'Import BUNI workbook records into the DTBi database.'

    def add_arguments(self, parser):
        parser.add_argument('--folder', default='static/style/buni')

    def handle(self, *args, **options):
        folder = Path(options['folder'])
        if not folder.exists():
            raise CommandError(f'BUNI folder does not exist: {folder}')

        counts = {'startups': 0, 'mentors': 0, 'investors': 0}
        for workbook_path in sorted(folder.glob('*.xlsx')):
            workbook = load_workbook(workbook_path, read_only=True, data_only=True)
            for sheet in workbook.worksheets:
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    continue
                if sheet.title.lower() == 'startups' or 'startup' in workbook_path.name.lower():
                    counts['startups'] += self.import_startups(rows, workbook_path.name)
                elif sheet.title.lower() == 'form responses':
                    counts['mentors'] += self.import_mentors(rows, workbook_path.name)
                else:
                    counts['investors'] += self.import_investors(rows, workbook_path.name)

        self.stdout.write(self.style.SUCCESS(
            'Imported or updated: '
            f"{counts['startups']} startups, {counts['mentors']} mentors, {counts['investors']} investors."
        ))

    @staticmethod
    def text(value):
        return str(value).strip() if value not in (None, '') else ''

    def import_startups(self, rows, source):
        imported = 0
        hidden_names = {
            'first name', 'on going projects', 'cyber security', 'real estate/services',
            'logistic', 'tourism', 'manufacturers', 'innovation clusters', 's/n',
        }
        for row in rows[1:]:
            values = [self.text(value) for value in row]
            if not any(values):
                continue
            name = next((value for value in values[1:5] if value), '')
            if not name or name.lower() in {'status', 'website'}:
                continue
            if name.lower() in hidden_names or name.isdigit() or len(name) > 120:
                continue
            website = values[0] if values and values[0].startswith(('http://', 'https://')) else ''
            description = next((value for value in values[1:] if len(value) > 40), '')
            email = next((value for value in values if '@' in value), '')
            phone = next((value for value in values if value.startswith('+255') or value.startswith('0')), '')
            startup, created = Startup.objects.get_or_create(name=name, defaults={
                'website': website,
                'description': description,
                'contact_email': email,
                'phone': phone,
                'source': source,
                'status': 'active',
            })
            changed = False
            if website and not startup.website:
                startup.website = website
                changed = True
            if description and not startup.description:
                startup.description = description
                changed = True
            if email and not startup.contact_email:
                startup.contact_email = email
                changed = True
            if phone and not startup.phone:
                startup.phone = phone
                changed = True
            if changed:
                startup.save(update_fields=['website', 'description', 'contact_email', 'phone', 'updated_at'])
            imported += int(created)
        return imported

    def import_mentors(self, rows, source):
        headers = [self.text(value).lower() for value in rows[0]]
        def find(*terms):
            return next((index for index, header in enumerate(headers) if any(term in header for term in terms)), None)

        name_indexes = [find('first name'), find('last name')]
        email_index = find('email')
        gender_index = find('gender')
        education_index = find('education')
        phone_index = find('phone')
        role_index = find('describe yourself')
        skills_index = find('skill set', 'skills that you possess')
        training_index = find('train people', 'trainer')
        imported = 0
        for row in rows[1:]:
            values = [self.text(value) for value in row]
            first = values[name_indexes[0]] if name_indexes[0] is not None and name_indexes[0] < len(values) else ''
            last = values[name_indexes[1]] if name_indexes[1] is not None and name_indexes[1] < len(values) else ''
            name = ' '.join(part for part in (first, last) if part)
            if not name:
                continue
            email = values[email_index] if email_index is not None and email_index < len(values) else ''
            mentor, created = Mentor.objects.get_or_create(name=name, email=email, defaults={
                'gender': values[gender_index] if gender_index is not None else '',
                'education_level': values[education_index] if education_index is not None else '',
                'phone': values[phone_index] if phone_index is not None else '',
                'role': values[role_index] if role_index is not None else '',
                'skills': values[skills_index] if skills_index is not None else '',
                'training_topics': values[training_index] if training_index is not None else '',
                'source': source,
            })
            imported += int(created)
        return imported

    def import_investors(self, rows, source):
        imported = 0
        for row in rows[1:]:
            values = [self.text(value) for value in row]
            name = next((value for value in values[:3] if value), '')
            if not name:
                continue
            email = next((value for value in values if '@' in value), '')
            Investor.objects.get_or_create(name=name, email=email, defaults={
                'description': next((value for value in values if len(value) > 40), ''),
                'source': source,
            })
            imported += 1
        return imported
