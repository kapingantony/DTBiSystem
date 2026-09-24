import csv
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from openpyxl import load_workbook

from .models import (
    DataImportBatch, Funding, Investor, KPI, Mentor, MentorEngagement, MentorEngagementHistory,
    PageVisit, Partnership, PartnershipHistory, Startup, StartupStatusHistory,
    ParticipantJourney, ParticipantJourneyHistory, ParticipantSupport,
    ParticipantFollowUp, ParticipantFollowUpHistory, ParticipantOutcome,
)


IMPORT_MODELS = {'startup': Startup, 'mentor': Mentor, 'investor': Investor, 'participant': ParticipantJourney}
IMPORT_FIELDS = {
    'startup': ('name', 'startup_type', 'description', 'industry', 'website', 'contact_email', 'phone', 'source', 'status', 'contract_status', 'founded_date', 'incubation_start', 'incubation_end', 'year_incubated'),
    'mentor': ('name', 'email', 'gender', 'education_level', 'phone', 'role', 'skills', 'training_topics', 'is_active', 'source'),
    'investor': ('name', 'organization', 'email', 'phone', 'website', 'description', 'investment_interest', 'status', 'source'),
    'participant': ('participant_name', 'email', 'phone', 'startup', 'current_stage', 'status', 'cohort', 'started_on'),
}
ALIASES = {
    'name': ('name', 'startup', 'startup name', 'company', 'company name', 'mentor name', 'investor name', 'full name', 'combined full name'),
    'participant_name': ('participant name', 'beneficiary name', 'full name', 'name', 'founder name'),
    'current_stage': ('current stage', 'programme stage', 'program stage', 'stage'),
    'cohort': ('cohort', 'batch', 'intake'),
    'started_on': ('started on', 'programme start date', 'program start date', 'enrolment date', 'enrollment date'),
    'startup': ('startup', 'startup name', 'company', 'company name'),
    'organization': ('organization', 'organisation', 'company', 'company name', 'fund'),
    'email': ('email', 'email address', 'contact email'),
    'contact_email': ('contact email', 'email', 'email address'),
    'industry': ('industry', 'sector'),
    'website': ('website', 'url', 'web address'),
    'phone': ('phone', 'telephone', 'mobile', 'contact number'),
    'description': ('description', 'profile', 'about', 'summary'),
    'status': ('status', 'startup status', 'investor status'),
    'startup_type': ('startup type', 'type'),
    'contract_status': ('contract status', 'contract'),
    'founded_date': ('founded date', 'date founded', 'year founded'),
    'incubation_start': ('incubation start', 'programme start', 'program start'),
    'incubation_end': ('incubation end', 'programme end', 'program end'),
    'year_incubated': ('year incubated', 'cohort year', 'incubation year'),
    'gender': ('gender',),
    'education_level': ('education', 'education level', 'qualification'),
    'role': ('role', 'mentor role', 'describe yourself'),
    'skills': ('skills', 'skill set', 'expertise'),
    'training_topics': ('training topics', 'topics', 'areas to train'),
    'investment_interest': ('investment interest', 'investment focus', 'interests'),
    'source': ('source', 'data source', 'programme'),
    'is_active': ('active', 'is active', 'status'),
}


def _normalize(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').strip().lower()).strip()


def read_import_file(path):
    """Return column headings and non-empty rows for CSV, XLSX, or tabular PDF."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.csv':
        try:
            handle = path.open('r', encoding='utf-8-sig', newline='')
            rows = list(csv.reader(handle))
        except UnicodeDecodeError:
            with path.open('r', encoding='cp1252', newline='') as handle:
                rows = list(csv.reader(handle))
        finally:
            if 'handle' in locals():
                handle.close()
    elif suffix == '.xlsx':
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            rows = list(workbook.active.iter_rows(values_only=True))
        finally:
            workbook.close()
    elif suffix == '.pdf':
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValidationError('PDF importing needs the declared pdfplumber dependency. Restart the app and install requirements.txt, then retry.') from exc
        rows = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                rows.extend(row for table in (page.extract_tables() or []) for row in table if row)
        if not rows:
            raise ValidationError('No tables could be read from this PDF. Use a text based PDF with a clear table, or convert it to Excel/CSV.')
    else:
        raise ValidationError('Upload an .xlsx, .csv, or table based .pdf file.')

    rows = [list(row) for row in rows if row and any(value not in (None, '') for value in row)]
    if len(rows) < 2:
        raise ValidationError('The file must contain a heading row and at least one data row.')
    headers = [str(value or '').strip() for value in rows[0]]
    if not any(headers):
        raise ValidationError('The first row must contain column headings.')
    records = []
    for row in rows[1:20001]:
        records.append({headers[index]: value for index, value in enumerate(row) if index < len(headers) and headers[index]})
    if not records:
        raise ValidationError('No data rows were found.')
    return headers, records


def guess_field_mapping(dataset, headers):
    normalized = {_normalize(header): header for header in headers}
    mapping = {}
    for field in IMPORT_FIELDS[dataset]:
        aliases = ALIASES.get(field, (field.replace('_', ' '),))
        found = next((normalized[_normalize(alias)] for alias in aliases if _normalize(alias) in normalized), None)
        if found:
            mapping[field] = found
    return mapping


def _value_for_field(raw, field):
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
    if raw == '':
        return None
    if field in {'founded_date', 'incubation_start', 'incubation_end', 'started_on'}:
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        value = str(raw).strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise ValidationError(f'Invalid date: {raw}')
    if field == 'year_incubated':
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            raise ValidationError(f'Invalid year: {raw}')
    if field == 'is_active':
        value = _normalize(raw)
        if value in {'yes', 'true', '1', 'active', 'y'}:
            return True
        if value in {'no', 'false', '0', 'inactive', 'n'}:
            return False
        raise ValidationError(f'Expected yes/no or active/inactive, got: {raw}')
    if field == 'current_stage' and isinstance(raw, str):
        choices = ParticipantJourney.STAGE_CHOICES
        normalized_choices = {_normalize(label): key for key, label in choices}
        normalized_choices.update({_normalize(key): key for key, _label in choices})
        choice = normalized_choices.get(_normalize(raw))
        if choice:
            return choice
        raise ValidationError(f'Unknown {field.replace("_", " ")}: {raw}')
    return str(raw).strip()


def _participant_status_value(raw):
    choices = {_normalize(label): key for key, label in ParticipantJourney.STATUS_CHOICES}
    choices.update({_normalize(key): key for key, _label in ParticipantJourney.STATUS_CHOICES})
    status = choices.get(_normalize(raw))
    if not status:
        raise ValidationError(f'Unknown participant status: {raw}')
    return status


def _identity_query(dataset, values):
    name = values.get('name')
    email = values.get('email') or values.get('contact_email')
    if dataset == 'startup':
        if email:
            return Startup.objects.filter(contact_email__iexact=email)
        return Startup.objects.filter(name__iexact=name)
    if dataset == 'mentor':
        if email:
            return Mentor.objects.filter(email__iexact=email)
        return Mentor.objects.filter(name__iexact=name)
    if dataset == 'participant':
        if email:
            return ParticipantJourney.objects.filter(email__iexact=email)
        return ParticipantJourney.objects.filter(
            participant_name__iexact=values.get('participant_name'),
            cohort__iexact=values.get('cohort', ''),
        )
    if email:
        return Investor.objects.filter(email__iexact=email)
    return Investor.objects.filter(name__iexact=name, organization__iexact=values.get('organization', ''))


def _identity_key(dataset, values):
    email = (values.get('email') or values.get('contact_email') or '').strip().casefold()
    if email:
        return dataset, 'email', email
    if dataset == 'participant':
        return dataset, 'name', _normalize(values.get('participant_name')), _normalize(values.get('cohort'))
    name = _normalize(values.get('name'))
    organization = _normalize(values.get('organization')) if dataset == 'investor' else ''
    return dataset, 'name', name, organization


def _resolve_import_values(dataset, values):
    if dataset != 'participant' or not values.get('startup'):
        return values
    startup_name = values['startup']
    matches = Startup.objects.filter(name__iexact=startup_name)
    if matches.count() != 1:
        raise ValidationError(f'Startup "{startup_name}" must match exactly one existing startup; it will not be created from this import.')
    values = dict(values)
    values['startup'] = matches.first()
    return values


def analyze_import_preview(batch, mapping):
    """Validate mapped rows without saving and classify likely creates/updates."""
    headers, rows = read_import_file(batch.file.path)
    if batch.dataset == 'mentor':
        normalized = {_normalize(header): header for header in headers}
        first_header, last_header = normalized.get('first name'), normalized.get('last name')
        if first_header and last_header and not any(_normalize(header) in {'name', 'full name', 'mentor name'} for header in headers):
            combined = 'Combined full name'
            headers.append(combined)
            for row in rows:
                row[combined] = ' '.join(str(row.get(key) or '').strip() for key in (first_header, last_header)).strip()

    selected = {field: header for field, header in mapping.items()
                if field in IMPORT_FIELDS[batch.dataset] and header in headers}
    required_name_field = 'participant_name' if batch.dataset == 'participant' else 'name'
    if required_name_field not in selected:
        return {'total': len(rows), 'creates': 0, 'updates': 0, 'issues': 1,
                'rows': [{'row': 1, 'status': 'issue', 'message': 'Map a file column to the required Name field.'}]}

    seen = set()
    creates = updates = issues = 0
    details = []
    model = IMPORT_MODELS[batch.dataset]
    for line, row in enumerate(rows, start=2):
        try:
            values = {field: value for field, header in selected.items()
                      if (value := _value_for_field(row.get(header), field)) is not None}
            if batch.dataset == 'participant' and 'status' in values:
                values['status'] = _participant_status_value(values['status'])
            values = _resolve_import_values(batch.dataset, values)
            if not values.get(required_name_field):
                raise ValidationError('Name is required.')
            key = _identity_key(batch.dataset, values)
            if key in seen:
                raise ValidationError('Duplicate identity in this file; only the first matching row can be imported.')
            seen.add(key)
            matches = _identity_query(batch.dataset, values)
            if matches.count() > 1:
                raise ValidationError('This identity matches multiple existing records; resolve duplicates first.')
            instance = matches.first() or model()
            for field, value in values.items():
                setattr(instance, field, value)
            if 'source' in IMPORT_FIELDS[batch.dataset] and not values.get('source'):
                instance.source = batch.original_filename
            instance.full_clean(exclude=['slug'] if batch.dataset == 'startup' else None)
            status = 'update' if instance.pk else 'create'
            if status == 'update':
                updates += 1
            else:
                creates += 1
            message = 'Would update an existing record.' if status == 'update' else 'Would create a new record.'
        except (ValidationError, InvalidOperation, ValueError, TypeError) as exc:
            issues += 1
            status = 'issue'
            message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        if status == 'issue':
            details.append({'row': line, 'status': status, 'message': message})
    return {'total': len(rows), 'creates': creates, 'updates': updates, 'issues': issues, 'rows': details}


def preview_import(batch):
    headers, rows = read_import_file(batch.file.path)
    if batch.dataset == 'mentor':
        normalized = {_normalize(header): header for header in headers}
        first_header = normalized.get('first name')
        last_header = normalized.get('last name')
        if first_header and last_header and not any(_normalize(header) in {'name', 'full name', 'mentor name'} for header in headers):
            combined = 'Combined full name'
            headers.append(combined)
            for row in rows:
                row[combined] = ' '.join(str(row.get(key) or '').strip() for key in (first_header, last_header)).strip()
    batch.headers = headers
    batch.total_rows = len(rows)
    if not batch.field_mapping:
        batch.field_mapping = guess_field_mapping(batch.dataset, headers)
    batch.save(update_fields=['headers', 'total_rows', 'field_mapping'])
    return headers, rows


def commit_import(batch, mapping):
    if batch.status == 'completed':
        raise ValidationError('This batch has already been imported.')
    headers, rows = read_import_file(batch.file.path)
    if batch.dataset == 'mentor':
        normalized = {_normalize(header): header for header in headers}
        first_header = normalized.get('first name')
        last_header = normalized.get('last name')
        if first_header and last_header and not any(_normalize(header) in {'name', 'full name', 'mentor name'} for header in headers):
            combined = 'Combined full name'
            headers.append(combined)
            for row in rows:
                row[combined] = ' '.join(str(row.get(key) or '').strip() for key in (first_header, last_header)).strip()
    model = IMPORT_MODELS[batch.dataset]
    allowed = set(IMPORT_FIELDS[batch.dataset])
    selected = {field: header for field, header in mapping.items() if field in allowed and header in headers}
    required_name_field = 'participant_name' if batch.dataset == 'participant' else 'name'
    if required_name_field not in selected:
        raise ValidationError('Map a file column to the required Name field before importing.')

    created = updated = skipped = 0
    errors = []
    seen = set()
    with transaction.atomic():
        for line, row in enumerate(rows, start=2):
            values = {}
            try:
                for field, header in selected.items():
                    value = _value_for_field(row.get(header), field)
                    if value is not None:
                        values[field] = value
                if batch.dataset == 'participant' and 'status' in values:
                    values['status'] = _participant_status_value(values['status'])
                values = _resolve_import_values(batch.dataset, values)
                if not values.get(required_name_field):
                    skipped += 1
                    errors.append({'row': line, 'error': 'Name is required.'})
                    continue
                identity = _identity_key(batch.dataset, values)
                if identity in seen:
                    skipped += 1
                    errors.append({'row': line, 'error': 'Duplicate identity in this file; only the first matching row was imported.'})
                    continue
                seen.add(identity)
                existing = _identity_query(batch.dataset, values)
                if existing.count() > 1:
                    skipped += 1
                    errors.append({'row': line, 'error': 'This identity matches multiple existing records; resolve duplicates before importing.'})
                    continue
                instance = existing.first() or model()
                was_created = instance.pk is None
                previous = (instance.current_stage, instance.status) if batch.dataset == 'participant' and instance.pk else ('', '')
                for field, value in values.items():
                    setattr(instance, field, value)
                if 'source' in allowed and not values.get('source'):
                    instance.source = batch.original_filename
                instance.full_clean(exclude=['slug'] if batch.dataset == 'startup' else None)
                instance.save()
                if batch.dataset == 'participant' and previous != (instance.current_stage, instance.status):
                    ParticipantJourneyHistory.objects.create(
                        journey=instance, old_stage=previous[0], new_stage=instance.current_stage,
                        old_status=previous[1], new_status=instance.status,
                        changed_by=batch.uploaded_by,
                        note='Imported current participant stage; earlier programme history was not inferred.'
                            if was_created else 'Stage/status updated by data import.',
                    )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except (ValidationError, InvalidOperation, ValueError, TypeError) as exc:
                skipped += 1
                message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                errors.append({'row': line, 'error': message})

    batch.status = 'completed'
    batch.field_mapping = selected
    batch.total_rows = len(rows)
    batch.created_count = created
    batch.updated_count = updated
    batch.skipped_count = skipped
    batch.row_errors = errors
    batch.completed_at = timezone.now()
    batch.save(update_fields=[
        'status', 'field_mapping', 'total_rows', 'created_count', 'updated_count',
        'skipped_count', 'row_errors', 'completed_at',
    ])
    return batch


def report_data(start_date, end_date):
    starts = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    ends = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    status_rows = list(StartupStatusHistory.objects.filter(recorded_at__range=(starts, ends)).values(
        'status', 'contract_status'
    ).annotate(total=Count('id')).order_by('status', 'contract_status'))
    funding_rows = list(Funding.objects.filter(created_at__range=(starts, ends)).values(
        'currency', 'status', 'investor__name', 'source', 'startup__name'
    ).annotate(total_amount=Sum('amount'), records=Count('id')).order_by('currency', 'status'))
    mentor_rows = list(MentorEngagement.objects.filter(date__range=(start_date, end_date)).values(
        'mentor__name', 'startup__name', 'date', 'hours', 'topics', 'outcome'
    ).filter(status='completed').order_by('-date'))
    scheduled_mentor_rows = list(MentorEngagement.objects.filter(
        date__range=(start_date, end_date), status__in=('scheduled', 'confirmed')
    ).values('mentor__name', 'startup__name', 'date', 'start_time', 'hours', 'topics', 'status', 'meeting_location', 'meeting_url').order_by('date', 'start_time'))
    mentor_session_changes = list(MentorEngagementHistory.objects.filter(changed_at__range=(starts, ends)).values(
        'engagement__mentor__name', 'engagement__startup__name', 'old_status', 'new_status',
        'old_date', 'old_start_time', 'new_date', 'new_start_time', 'note', 'changed_at',
    ).order_by('-changed_at'))
    visit_rows = list(PageVisit.objects.filter(visited_at__range=(starts, ends)).values(
        'page_type', 'display_name'
    ).annotate(visits=Count('id')).order_by('-visits', 'display_name'))
    funding_totals = {}
    for row in funding_rows:
        funding_totals[row['currency']] = funding_totals.get(row['currency'], Decimal('0')) + (row['total_amount'] or Decimal('0'))
    duration = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    previous_start_dt = timezone.make_aware(datetime.combine(previous_start, datetime.min.time()))
    previous_end_dt = timezone.make_aware(datetime.combine(previous_end, datetime.max.time()))
    previous_startups = Startup.objects.filter(created_at__range=(previous_start_dt, previous_end_dt)).count()
    new_startups = Startup.objects.filter(created_at__range=(starts, ends)).count()
    partnership_rows = list(Partnership.objects.filter(created_at__range=(starts, ends)).values(
        'organization', 'startup_name', 'partnership_type', 'status',
        'related_startup__name', 'startup_benefit', 'expected_outcomes',
        'assigned_to__username', 'created_at',
    ).order_by('-created_at'))
    partnership_type_labels = dict(Partnership.TYPE_CHOICES)
    for row in partnership_rows:
        row['partnership_type_display'] = partnership_type_labels.get(row['partnership_type'], row['partnership_type'])
    partnership_history = list(PartnershipHistory.objects.filter(changed_at__range=(starts, ends)).values(
        'partnership__organization', 'partnership__startup_name', 'old_status', 'new_status', 'changed_at',
    ).order_by('-changed_at'))
    partnership_statuses = list(Partnership.objects.values('status').annotate(total=Count('id')).order_by('status'))
    active_partnership_pipeline = Partnership.objects.filter(
        status__in=('pending', 'under_review', 'approved', 'in_progress', 'on_hold')
    ).count()
    journey_stage_counts = list(ParticipantJourney.objects.values('current_stage').annotate(total=Count('id')).order_by('current_stage'))
    journey_changes = list(ParticipantJourneyHistory.objects.filter(changed_at__range=(starts, ends)).values(
        'journey__participant_name', 'journey__startup__name', 'old_stage', 'new_stage',
        'old_status', 'new_status', 'changed_by__username', 'note', 'changed_at',
    ).order_by('-changed_at'))
    journey_stage_labels = dict(ParticipantJourney.STAGE_CHOICES)
    for row in journey_stage_counts:
        row['current_stage_display'] = journey_stage_labels.get(row['current_stage'], row['current_stage'])
    for row in journey_changes:
        row['old_stage_display'] = journey_stage_labels.get(row['old_stage'], row['old_stage'] or 'New')
        row['new_stage_display'] = journey_stage_labels.get(row['new_stage'], row['new_stage'])
    support_rows = list(ParticipantSupport.objects.filter(delivered_on__range=(start_date, end_date)).values(
        'journey__participant_name', 'journey__startup__name', 'support_type', 'title',
        'delivered_on', 'provider', 'hours',
    ).order_by('-delivered_on'))
    support_labels = dict(ParticipantSupport.SUPPORT_CHOICES)
    for row in support_rows:
        row['support_type_display'] = support_labels.get(row['support_type'], row['support_type'])
    support_by_type = list(ParticipantSupport.objects.filter(delivered_on__range=(start_date, end_date)).values(
        'support_type'
    ).annotate(total=Count('id'), total_hours=Sum('hours')).order_by('support_type'))
    for row in support_by_type:
        row['support_type_display'] = support_labels.get(row['support_type'], row['support_type'])
    outcome_rows = list(ParticipantOutcome.objects.filter(recorded_on__range=(start_date, end_date)).values(
        'journey_id', 'journey__participant_name', 'journey__startup__name', 'recorded_on',
        'full_time_jobs', 'part_time_jobs', 'monthly_revenue', 'revenue_currency',
        'customers_or_users', 'milestone',
    ).order_by('-recorded_on', 'journey__participant_name'))
    all_outcomes = list(ParticipantOutcome.objects.filter(recorded_on__lte=end_date).values(
        'journey_id', 'recorded_on', 'full_time_jobs', 'part_time_jobs',
        'monthly_revenue', 'revenue_currency', 'customers_or_users',
    ).order_by('journey_id', 'recorded_on', 'id'))
    snapshots_by_journey = {}
    for snapshot in all_outcomes:
        snapshots_by_journey.setdefault(snapshot['journey_id'], []).append(snapshot)
    outcome_comparisons = []
    outcome_change_totals = {'full_time_jobs': 0, 'part_time_jobs': 0, 'customers_or_users': 0, 'revenue_by_currency': {}}
    for journey_id, snapshots in snapshots_by_journey.items():
        baseline = next((snap for snap in reversed(snapshots) if snap['recorded_on'] < start_date), None)
        current = next((snap for snap in reversed(snapshots) if snap['recorded_on'] >= start_date), None)
        if not baseline or not current:
            continue
        delta = {
            'full_time_jobs': current['full_time_jobs'] - baseline['full_time_jobs'],
            'part_time_jobs': current['part_time_jobs'] - baseline['part_time_jobs'],
            'customers_or_users': (current['customers_or_users'] - baseline['customers_or_users'])
                if current['customers_or_users'] is not None and baseline['customers_or_users'] is not None else None,
            'revenue_currency': current['revenue_currency'],
            'monthly_revenue': None,
        }
        if current['monthly_revenue'] is not None and baseline['monthly_revenue'] is not None and current['revenue_currency'] == baseline['revenue_currency']:
            delta['monthly_revenue'] = current['monthly_revenue'] - baseline['monthly_revenue']
            currency = delta['revenue_currency']
            outcome_change_totals['revenue_by_currency'][currency] = outcome_change_totals['revenue_by_currency'].get(currency, Decimal('0')) + delta['monthly_revenue']
        outcome_change_totals['full_time_jobs'] += delta['full_time_jobs']
        outcome_change_totals['part_time_jobs'] += delta['part_time_jobs']
        if delta['customers_or_users'] is not None:
            outcome_change_totals['customers_or_users'] += delta['customers_or_users']
        outcome_comparisons.append(delta)
    followups_due = ParticipantFollowUp.objects.filter(
        due_date__range=(start_date, end_date), status__in=('open', 'in_progress'),
    ).count()
    followups_completed = ParticipantFollowUpHistory.objects.filter(
        new_status='done', changed_at__range=(starts, ends),
    ).count()
    if new_startups > previous_startups:
        activity_signal = f'Startup registrations increased by {new_startups - previous_startups} compared with the previous equal-length period.'
    elif new_startups < previous_startups:
        activity_signal = f'Startup registrations decreased by {previous_startups - new_startups} compared with the previous equal-length period.'
    else:
        activity_signal = 'Startup registrations were unchanged compared with the previous equal-length period.'
    return {
        'start_date': start_date,
        'end_date': end_date,
        'new_startups': new_startups,
        'previous_startups': previous_startups,
        'activity_signal': activity_signal,
        'new_partnerships': len(partnership_rows),
        'active_partnership_pipeline': active_partnership_pipeline,
        'completed_partnerships': PartnershipHistory.objects.filter(
            new_status='completed', changed_at__range=(starts, ends)
        ).count(),
        'partnership_statuses': partnership_statuses,
        'partnership_rows': partnership_rows,
        'partnership_history': partnership_history,
        'startups_by_status': list(Startup.objects.values('status').annotate(total=Count('id')).order_by('status')),
        'status_changes': status_rows,
        'new_mentors': Mentor.objects.filter(created_at__range=(starts, ends)).count(),
        'new_investors': Investor.objects.filter(created_at__range=(starts, ends)).count(),
        'funding': funding_rows,
        'funding_totals': funding_totals,
        'kpi_observations': KPI.objects.filter(date_recorded__range=(start_date, end_date)).count(),
        'mentor_sessions': len(mentor_rows),
        'mentor_hours': sum((row['hours'] or Decimal('0')) for row in mentor_rows),
        'mentor_rows': mentor_rows,
        'scheduled_mentor_sessions': len(scheduled_mentor_rows),
        'scheduled_mentor_rows': scheduled_mentor_rows,
        'mentor_session_changes': mentor_session_changes,
        'cancelled_mentor_sessions': MentorEngagementHistory.objects.filter(
            new_status__in=('cancelled', 'no_show'), changed_at__range=(starts, ends)
        ).count(),
        'page_visits': visit_rows,
        'page_visit_total': sum(row['visits'] for row in visit_rows),
        'participant_journeys_current': ParticipantJourney.objects.count(),
        'participant_journeys_by_stage': journey_stage_counts,
        'participant_journey_changes': journey_changes,
        'participant_support_total': len(support_rows),
        'participant_support_rows': support_rows,
        'participant_support_by_type': support_by_type,
        'participant_outcome_snapshots': outcome_rows,
        'participant_outcome_comparisons': len(outcome_comparisons),
        'participant_outcome_changes': outcome_change_totals,
        'participant_followups_due': followups_due,
        'participant_followups_completed': followups_completed,
    }
