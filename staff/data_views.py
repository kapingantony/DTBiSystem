import csv
import io
from datetime import date, datetime, timedelta, timezone as dt_timezone
from functools import wraps
from html import escape
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook

from .data_services import (
    IMPORT_FIELDS, IMPORT_MODELS, analyze_import_preview, commit_import,
    preview_import, report_data,
)
from .forms import (
    MentorEngagementScheduleForm, ParticipantJourneyForm, ParticipantSupportForm,
    ParticipantFollowUpForm, ParticipantOutcomeForm,
)
from .models import (
    DataImportBatch, Investor, Mentor, MentorEngagement, MentorEngagementHistory, PageVisit, Partnership,
    PartnershipHistory, Startup, UserProfile, ParticipantJourney,
    ParticipantJourneyHistory, ParticipantSupport, ParticipantFollowUp, ParticipantFollowUpHistory, ParticipantOutcome,
)
from .report_ai import summarize_report


def staff_or_admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        allowed = request.user.is_superuser or UserProfile.objects.filter(
            user=request.user, user_type__in=('admin', 'staff')
        ).exists()
        if not allowed:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        allowed = request.user.is_superuser or UserProfile.objects.filter(
            user=request.user, user_type='admin'
        ).exists()
        if not allowed:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def record_page_visit(request, page_type, object_key, display_name):
    if not request.session.session_key:
        request.session.create()
    PageVisit.objects.get_or_create(
        page_type=page_type,
        object_key=str(object_key),
        session_key=request.session.session_key,
        visit_date=timezone.localdate(),
        defaults={
            'display_name': str(display_name)[:255],
            'visitor': request.user if request.user.is_authenticated else None,
        },
    )


@staff_or_admin_required
def data_hub(request):
    partnership_pipeline = Partnership.objects.filter(status__in=('pending', 'under_review')).count()
    upcoming_session_count = MentorEngagement.objects.filter(
        status__in=('scheduled', 'confirmed'), date__gte=timezone.localdate()
    ).count()
    return render(request, 'data_hub.html', {
        'recent_imports': DataImportBatch.objects.select_related('uploaded_by')[:8],
        'unread_visits': PageVisit.objects.filter(is_read=False).count(),
        'is_admin': request.user.is_superuser or UserProfile.objects.filter(user=request.user, user_type='admin').exists(),
        'partnership_pipeline': partnership_pipeline,
        'upcoming_session_count': upcoming_session_count,
    })


@staff_or_admin_required
@require_http_methods(['GET', 'POST'])
def partnership_inbox(request):
    status_choices = dict(Partnership.STATUS_CHOICES)
    type_choices = dict(Partnership.TYPE_CHOICES)
    if request.method == 'POST':
        partnership = get_object_or_404(Partnership, pk=request.POST.get('partnership_id'))
        new_status = request.POST.get('status', '')
        if new_status not in status_choices:
            messages.error(request, 'Choose a valid partnership status.')
            return redirect(request.get_full_path())

        User = get_user_model()
        assignee_id = request.POST.get('assigned_to') or None
        valid_staff_ids = UserProfile.objects.filter(user_type__in=('admin', 'staff')).values_list('user_id', flat=True)
        assigned_to = None
        if assignee_id:
            assigned_to = User.objects.filter(pk=assignee_id).filter(
                Q(is_superuser=True) | Q(pk__in=valid_staff_ids)
            ).first()
            if assigned_to is None:
                messages.error(request, 'Choose an active staff or admin account for assignment.')
                return redirect(request.get_full_path())

        old_status = partnership.status
        partnership.status = new_status
        partnership.assigned_to = assigned_to
        partnership.review_notes = request.POST.get('review_notes', '').strip()
        partnership.save(update_fields=['status', 'assigned_to', 'review_notes', 'updated_at'])
        if old_status != new_status:
            PartnershipHistory.objects.create(
                partnership=partnership,
                old_status=old_status,
                new_status=new_status,
                changed_by=request.user,
                note=partnership.review_notes,
            )
        messages.success(request, f'Partnership request from {partnership.startup_name} updated.')
        return redirect(request.get_full_path())

    partnerships = Partnership.objects.select_related('related_startup', 'assigned_to').all()
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    search = request.GET.get('q', '').strip()
    if status_filter in status_choices:
        partnerships = partnerships.filter(status=status_filter)
    if type_filter in type_choices:
        partnerships = partnerships.filter(partnership_type=type_filter)
    if search:
        partnerships = partnerships.filter(
            Q(startup_name__icontains=search) | Q(organization__icontains=search)
            | Q(contact_name__icontains=search) | Q(email__icontains=search)
            | Q(related_startup__name__icontains=search)
        )
    totals = {row['status']: row['total'] for row in Partnership.objects.values('status').annotate(total=Count('id'))}
    User = get_user_model()
    staff_ids = UserProfile.objects.filter(user_type__in=('admin', 'staff')).values_list('user_id', flat=True)
    assignees = User.objects.filter(Q(is_superuser=True) | Q(pk__in=staff_ids)).distinct().order_by('username')
    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_obj = Paginator(partnerships, 20).get_page(request.GET.get('page'))
    return render(request, 'partnership_inbox.html', {
        'partnerships': page_obj,
        'page_obj': page_obj,
        'page_query': query_params.urlencode(),
        'status_choices': Partnership.STATUS_CHOICES,
        'type_choices': Partnership.TYPE_CHOICES,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search': search,
        'totals': totals,
        'assignees': assignees,
        'history': PartnershipHistory.objects.select_related('partnership', 'changed_by')[:30],
    })


@staff_or_admin_required
@require_http_methods(['GET', 'POST'])
def data_import(request):
    batch = None
    headers = []
    rows = []
    mapping = {}
    preview_analysis = None
    if request.method == 'POST' and request.POST.get('action') in {'check', 'confirm'}:
        batch = get_object_or_404(DataImportBatch, pk=request.POST.get('batch_id'), uploaded_by=request.user)
        mapping = {field: request.POST.get(f'map_{field}', '') for field in IMPORT_FIELDS[batch.dataset]}
        mapping = {field: header for field, header in mapping.items() if header}
        if request.POST.get('action') == 'check':
            try:
                preview_analysis = analyze_import_preview(batch, mapping)
                batch.field_mapping = mapping
                batch.row_errors = [
                    {'row': row['row'], 'error': row['message']}
                    for row in preview_analysis['rows'] if row['status'] == 'issue'
                ][:500]
                batch.save(update_fields=['field_mapping', 'row_errors'])
                headers, rows = preview_import(batch)
            except (ValidationError, OSError, ValueError) as exc:
                messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        else:
            try:
                commit_import(batch, mapping)
                messages.success(request, f'Import complete: {batch.created_count} created, {batch.updated_count} updated, {batch.skipped_count} skipped.')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
            return redirect(f'{request.path}?batch={batch.pk}')

    if request.method == 'GET' and request.GET.get('errors'):
        batch = get_object_or_404(DataImportBatch, pk=request.GET.get('errors'))
        if batch.uploaded_by_id != request.user.id and not request.user.is_superuser:
            raise PermissionDenied
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="import-{batch.pk}-errors.csv"'
        writer = csv.writer(response)
        writer.writerow(['Row', 'Issue'])
        writer.writerows((item.get('row', ''), item.get('error', '')) for item in batch.row_errors)
        return response

    if request.method == 'POST':
        dataset = request.POST.get('dataset', '')
        uploaded_file = request.FILES.get('file')
        if dataset not in IMPORT_FIELDS or not uploaded_file:
            messages.error(request, 'Choose a data type and a file to upload.')
        elif uploaded_file.size > 20 * 1024 * 1024:
            messages.error(request, 'Files must be 20 MB or smaller.')
        elif Path(uploaded_file.name).suffix.lower() not in {'.xlsx', '.csv', '.pdf'}:
            messages.error(request, 'Upload an Excel (.xlsx), CSV, or table based PDF file.')
        else:
            batch = DataImportBatch.objects.create(
                dataset=dataset,
                file=uploaded_file,
                original_filename=Path(uploaded_file.name).name[:255],
                uploaded_by=request.user,
            )
            try:
                headers, rows = preview_import(batch)
                mapping = batch.field_mapping
            except (ValidationError, OSError, ValueError) as exc:
                batch.status = 'failed'
                batch.row_errors = [{'row': 0, 'error': '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)}]
                batch.save(update_fields=['status', 'row_errors'])
                messages.error(request, batch.row_errors[0]['error'])

    batch_id = request.GET.get('batch')
    if batch is None and batch_id:
        batch = get_object_or_404(DataImportBatch, pk=batch_id, uploaded_by=request.user)
    if batch and batch.status == 'preview' and not headers:
        try:
            headers, rows = preview_import(batch)
            mapping = batch.field_mapping
        except (ValidationError, OSError, ValueError) as exc:
            messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    field_keys = IMPORT_FIELDS[batch.dataset] if batch else ()
    field_labels = {
        key: IMPORT_MODELS[batch.dataset]._meta.get_field(key).verbose_name.title()
        for key in field_keys
    } if batch else {}
    return render(request, 'data_import.html', {
        'batch': batch,
        'headers': headers,
        'sample_rows': [[row.get(header, '') for header in headers] for row in rows[:8]],
        'mapping': mapping,
        'mapping_fields': [{'key': key, 'label': field_labels[key], 'selected': mapping.get(key, '')} for key in field_keys],
        'datasets': DataImportBatch.DATASETS,
        'preview_analysis': preview_analysis,
        'preview_issue_rows': [row for row in (preview_analysis or {}).get('rows', []) if row['status'] == 'issue'][:30],
    })


def _period_dates(request):
    today = timezone.localdate()
    period = request.GET.get('period', 'month')
    if period == 'week':
        start = today - timedelta(days=today.weekday())
        end = min(start + timedelta(days=6), today)
    elif period == 'half_year':
        start = date(today.year, 1 if today.month <= 6 else 7, 1)
        end = min(date(today.year, 6 if today.month <= 6 else 12, 30 if today.month <= 6 else 31), today)
    elif period == 'year':
        start, end = date(today.year, 1, 1), today
    elif period == 'custom':
        try:
            start = date.fromisoformat(request.GET.get('from', ''))
            end = date.fromisoformat(request.GET.get('to', ''))
            if end < start:
                raise ValueError
        except ValueError:
            start, end, period = today.replace(day=1), today, 'month'
    else:
        start, end = today.replace(day=1), today
        period = 'month'
    return period, start, end


def _report_xlsx(data):
    book = Workbook()
    summary = book.active
    summary.title = 'Summary'
    summary.append(['DTBi / BUNI Programme Report', f"{data['start_date']} to {data['end_date']}"])
    for label, value in [
        ('New startups', data['new_startups']), ('Current startups', sum(r['total'] for r in data['startups_by_status'])),
        ('New mentors', data['new_mentors']), ('New investors', data['new_investors']),
        ('KPI observations recorded', data['kpi_observations']), ('Mentor sessions', data['mentor_sessions']),
        ('Mentor hours', data['mentor_hours']), ('Tracked page visits', data['page_visit_total']),
        ('Scheduled mentor sessions in period', data['scheduled_mentor_sessions']),
        ('Mentor cancellations / no-shows', data['cancelled_mentor_sessions']),
        ('New partnership requests', data['new_partnerships']),
        ('Active partnership pipeline', data['active_partnership_pipeline']),
        ('Partnerships completed in period', data['completed_partnerships']),
        ('Participant journeys currently tracked', data['participant_journeys_current']),
        ('Participant stage/status changes in period', len(data['participant_journey_changes'])),
        ('Additional support records in period', data['participant_support_total']),
        ('Open follow-ups due in period', data['participant_followups_due']),
        ('Follow-ups completed in period', data['participant_followups_completed']),
        ('Participants with comparable outcome snapshots', data['participant_outcome_comparisons']),
        ('Change in full-time jobs across comparable participants', data['participant_outcome_changes']['full_time_jobs']),
        ('Change in part-time jobs across comparable participants', data['participant_outcome_changes']['part_time_jobs']),
        ('Change in customers/users across comparable participants', data['participant_outcome_changes']['customers_or_users']),
    ]:
        summary.append([label, value])
    for currency, amount in sorted(data['funding_totals'].items()):
        summary.append([f'Funding recorded ({currency})', amount])
    for currency, amount in sorted(data['participant_outcome_changes']['revenue_by_currency'].items()):
        summary.append([f'Monthly revenue change across comparable participants ({currency})', amount])
    summary.append(['Activity signal (rule based)', data['activity_signal']])
    summary.append(['Executive summary source', data['executive_summary_source']])
    summary.append(['Executive summary', data['executive_summary']])
    for title, headers, rows in [
        ('Startup status', ['Status', 'Current count'], [(r['status'], r['total']) for r in data['startups_by_status']]),
        ('Participant stages today', ['Stage', 'Current participants'], [(r['current_stage_display'], r['total']) for r in data['participant_journeys_by_stage']]),
        ('Status history', ['Startup status', 'Contract status', 'Events'], [(r['status'], r['contract_status'], r['total']) for r in data['status_changes']]),
        ('Funding', ['Startup', 'Currency', 'Status', 'Investor', 'Source', 'Amount', 'Records'], [(r['startup__name'], r['currency'], r['status'], r['investor__name'] or '', r['source'], r['total_amount'], r['records']) for r in data['funding']]),
        ('Mentor sessions', ['Mentor', 'Startup', 'Date', 'Hours', 'Topics', 'Outcome'], [(r['mentor__name'], r['startup__name'], r['date'], r['hours'], r['topics'], r['outcome']) for r in data['mentor_rows']]),
        ('Scheduled mentor sessions', ['Mentor', 'Startup', 'Date', 'Time', 'Hours', 'Status', 'Location / link', 'Topics'], [(r['mentor__name'], r['startup__name'], r['date'], r['start_time'], r['hours'], r['status'], r['meeting_url'] or r['meeting_location'], r['topics']) for r in data['scheduled_mentor_rows']]),
        ('Mentor session history', ['Mentor', 'Startup', 'Previous status', 'New status', 'Previous date/time', 'New date/time', 'Changed at', 'Note'], [(r['engagement__mentor__name'], r['engagement__startup__name'], r['old_status'] or 'created', r['new_status'], f"{r['old_date'] or ''} {r['old_start_time'] or ''}", f"{r['new_date']} {r['new_start_time'] or ''}", r['changed_at'], r['note']) for r in data['mentor_session_changes']]),
        ('Page visits', ['Page type', 'Record', 'Unique daily visits'], [(r['page_type'], r['display_name'], r['visits']) for r in data['page_visits']]),
        ('Partnership requests', ['Organization', 'Request name', 'Type', 'Status', 'Related startup', 'Expected outcomes', 'Assigned to', 'Submitted'], [(r['organization'], r['startup_name'], r['partnership_type_display'], r['status'], r['related_startup__name'] or 'Programme-wide', r['expected_outcomes'], r['assigned_to__username'] or '', r['created_at']) for r in data['partnership_rows']]),
        ('Partnership status history', ['Organization', 'Request', 'Previous status', 'New status', 'Changed at'], [(r['partnership__organization'], r['partnership__startup_name'], r['old_status'] or 'submitted', r['new_status'], r['changed_at']) for r in data['partnership_history']]),
        ('Participant journey changes', ['Participant', 'Startup', 'Previous stage', 'New stage', 'Previous status', 'New status', 'Changed by', 'Changed at', 'Note'], [(r['journey__participant_name'], r['journey__startup__name'] or '', r['old_stage_display'], r['new_stage_display'], r['old_status'] or '', r['new_status'], r['changed_by__username'] or '', r['changed_at'], r['note']) for r in data['participant_journey_changes']]),
        ('Additional support', ['Participant', 'Startup', 'Support type', 'Activity', 'Date', 'Provider', 'Hours'], [(r['journey__participant_name'], r['journey__startup__name'] or '', r['support_type_display'], r['title'], r['delivered_on'], r['provider'], r['hours']) for r in data['participant_support_rows']]),
        ('Outcome snapshots', ['Participant', 'Startup', 'As of', 'Full-time jobs', 'Part-time jobs', 'Monthly revenue', 'Currency', 'Customers/users', 'Milestone'], [(r['journey__participant_name'], r['journey__startup__name'] or '', r['recorded_on'], r['full_time_jobs'], r['part_time_jobs'], r['monthly_revenue'], r['revenue_currency'], r['customers_or_users'], r['milestone']) for r in data['participant_outcome_snapshots']]),
    ]:
        sheet = book.create_sheet(title)
        sheet.append(headers)
        for row in rows:
            sheet.append(list(row))
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def _report_pdf(data):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValidationError('PDF report export needs the declared reportlab dependency. Restart the app and install requirements.txt, then retry.') from exc
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), title='DTBi / BUNI Programme Report')
    styles = getSampleStyleSheet()
    story = [Paragraph('DTBi / BUNI Programme Report', styles['Title']), Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']), Spacer(1, 14)]
    story.extend([Paragraph('Executive summary', styles['Heading2']),
                  Paragraph(escape(data['executive_summary']), styles['BodyText']),
                  Paragraph(f"Source: {escape(data['executive_summary_source'])}", styles['Italic']), Spacer(1, 10)])
    summary = [
        ['Measure', 'Result'], ['New startups', str(data['new_startups'])],
        ['Current startups', str(sum(r['total'] for r in data['startups_by_status']))],
        ['New mentors', str(data['new_mentors'])], ['New investors', str(data['new_investors'])],
        ['Mentor sessions / hours', f"{data['mentor_sessions']} / {data['mentor_hours']}"],
        ['Scheduled mentor sessions in period', str(data['scheduled_mentor_sessions'])],
        ['Mentor cancellations / no-shows', str(data['cancelled_mentor_sessions'])],
        ['KPI observations', str(data['kpi_observations'])], ['Tracked daily page visits', str(data['page_visit_total'])],
        ['New partnership requests', str(data['new_partnerships'])],
        ['Active partnership pipeline', str(data['active_partnership_pipeline'])],
        ['Partnerships completed in period', str(data['completed_partnerships'])],
        ['Participant journeys currently tracked', str(data['participant_journeys_current'])],
        ['Participant stage/status changes', str(len(data['participant_journey_changes']))],
        ['Additional support records', str(data['participant_support_total'])],
        ['Open follow-ups due in period', str(data['participant_followups_due'])],
        ['Follow-ups completed in period', str(data['participant_followups_completed'])],
        ['Participants with comparable outcome snapshots', str(data['participant_outcome_comparisons'])],
        ['Change in full-time jobs (comparable participants)', str(data['participant_outcome_changes']['full_time_jobs'])],
        ['Change in part-time jobs (comparable participants)', str(data['participant_outcome_changes']['part_time_jobs'])],
        ['Change in customers/users (comparable participants)', str(data['participant_outcome_changes']['customers_or_users'])],
    ]
    summary.extend([[f'Funding recorded ({currency})', str(amount)] for currency, amount in sorted(data['funding_totals'].items())])
    summary.extend([[f'Monthly revenue change ({currency})', str(amount)] for currency, amount in sorted(data['participant_outcome_changes']['revenue_by_currency'].items())])
    table = Table(summary, colWidths=[260, 400], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#12304a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#ccd5df')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f8')]),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))
    for heading, headers, rows in [
        ('Funding details', ['Startup', 'Currency', 'Status', 'Investor / source', 'Amount'], [
            (row['startup__name'], row['currency'], row['status'], row['investor__name'] or row['source'], str(row['total_amount']))
            for row in data['funding']
        ]),
        ('Mentor sessions', ['Date', 'Mentor', 'Startup', 'Hours', 'Topics'], [
            (str(row['date']), row['mentor__name'], row['startup__name'], str(row['hours']), (row['topics'] or '')[:90])
            for row in data['mentor_rows']
        ]),
        ('Scheduled mentor sessions', ['Date', 'Time', 'Mentor', 'Startup', 'Duration', 'Status', 'Location'], [
            (str(row['date']), str(row['start_time']), row['mentor__name'], row['startup__name'],
             f"{row['hours']} hours", row['status'], row['meeting_url'] or row['meeting_location'])
            for row in data['scheduled_mentor_rows']
        ]),
        ('Mentor session changes', ['Mentor / startup', 'Status change', 'Previous schedule', 'Current schedule', 'Changed at'], [
            (f"{row['engagement__mentor__name']} / {row['engagement__startup__name']}",
             f"{row['old_status'] or 'created'} -> {row['new_status']}",
             f"{row['old_date'] or ''} {row['old_start_time'] or ''}",
             f"{row['new_date']} {row['new_start_time'] or ''}", str(row['changed_at']))
            for row in data['mentor_session_changes']
        ]),
        ('Page visits', ['Record', 'Type', 'Unique daily visits'], [
            (row['display_name'], row['page_type'], str(row['visits'])) for row in data['page_visits']
        ]),
        ('Partnership requests', ['Organization / request', 'Area', 'Status', 'Startup', 'Expected outcome'], [
            (row['organization'] or row['startup_name'], row['partnership_type_display'], row['status'],
             row['related_startup__name'] or 'Programme-wide', (row['expected_outcomes'] or '')[:140])
            for row in data['partnership_rows']
        ]),
        ('Participant progress', ['Participant', 'Stage change', 'Status change', 'Changed at'], [
            (row['journey__participant_name'], f"{row['old_stage_display']} -> {row['new_stage_display']}",
             f"{row['old_status'] or 'new'} -> {row['new_status']}", str(row['changed_at']))
            for row in data['participant_journey_changes']
        ]),
        ('Additional support', ['Participant', 'Type', 'Activity', 'Date', 'Provider', 'Hours'], [
            (row['journey__participant_name'], row['support_type_display'], row['title'], str(row['delivered_on']), row['provider'], str(row['hours'] or ''))
            for row in data['participant_support_rows']
        ]),
        ('Outcome snapshots', ['Participant', 'As of', 'Full-time jobs', 'Part-time jobs', 'Monthly revenue', 'Currency', 'Customers/users', 'Milestone'], [
            (row['journey__participant_name'], str(row['recorded_on']), str(row['full_time_jobs']), str(row['part_time_jobs']), str(row['monthly_revenue'] or ''), row['revenue_currency'], str(row['customers_or_users'] if row['customers_or_users'] is not None else ''), row['milestone'])
            for row in data['participant_outcome_snapshots']
        ]),
    ]:
        story.append(Paragraph(heading, styles['Heading2']))
        if rows:
            detail_table = Table([headers] + [list(row) for row in rows], repeatRows=1)
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#12304a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#ccd5df')),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(detail_table)
        else:
            story.append(Paragraph('No records in this period.', styles['BodyText']))
        story.append(Spacer(1, 10))
    story.append(Paragraph('Interpretation notes', styles['Heading2']))
    story.append(Paragraph('Counts reflect records and events currently recorded in the system. Historical status tracking, partnership status history, and mentorship reporting begin when those features are introduced; this report does not infer earlier events. Funding totals retain the currency of each record and must be compared within currency.', styles['BodyText']))
    story.append(Spacer(1, 8))
    story.append(Paragraph('Automated activity signal (rule based, not AI generated): ' + data['activity_signal'], styles['BodyText']))
    doc.build(story)
    return output.getvalue()


@staff_or_admin_required
def data_reports(request):
    period, start, end = _period_dates(request)
    data = report_data(start, end)
    summary = summarize_report(data)
    data['executive_summary'] = summary['text']
    data['executive_summary_source'] = summary['source']
    data['ai_enabled'] = summary['ai_enabled']
    fmt = request.GET.get('format')
    if fmt == 'xlsx':
        response = HttpResponse(_report_xlsx(data), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="dtbi-report-{start}-{end}.xlsx"'
        return response
    if fmt == 'pdf':
        try:
            pdf = _report_pdf(data)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('staff:data_reports')
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="dtbi-report-{start}-{end}.pdf"'
        return response
    data.update({'period': period, 'presets': ('week', 'month', 'half_year', 'year', 'custom')})
    return render(request, 'data_reports.html', data)


@admin_required
@require_http_methods(['GET', 'POST'])
def page_visit_admin(request):
    if request.method == 'POST' and request.POST.get('action') == 'mark_read':
        PageVisit.objects.filter(is_read=False).update(is_read=True)
        messages.success(request, 'Page visit notifications marked as read.')
        return redirect('staff:page_visit_admin')
    visits = PageVisit.objects.select_related('visitor').all()
    page_type = request.GET.get('type', '')
    search = request.GET.get('q', '').strip()
    if page_type in {'startup', 'mentor', 'investor'}:
        visits = visits.filter(page_type=page_type)
    if search:
        visits = visits.filter(Q(display_name__icontains=search) | Q(visitor__username__icontains=search))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_obj = Paginator(visits, 50).get_page(request.GET.get('page'))
    return render(request, 'page_visit_admin.html', {
        'visits': page_obj,
        'page_obj': page_obj,
        'page_query': query_params.urlencode(),
        'unread_count': PageVisit.objects.filter(is_read=False).count(),
        'page_type': page_type,
        'search': search,
    })


@staff_or_admin_required
@require_http_methods(['GET', 'POST'])
def mentor_sessions(request):
    form = MentorEngagementScheduleForm(initial={'mentor': request.GET.get('mentor')})
    if request.method == 'POST' and request.POST.get('action') == 'schedule':
        form = MentorEngagementScheduleForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.scheduled_by = request.user
            session.full_clean()
            session.save()
            MentorEngagementHistory.objects.create(
                engagement=session,
                old_status='',
                new_status=session.status,
                new_date=session.date,
                new_start_time=session.start_time,
                changed_by=request.user,
                note='Session arranged.',
            )
            messages.success(request, f'Session scheduled with {session.mentor} for {session.startup} on {session.date}.')
            return redirect('staff:mentor_sessions')
    elif request.method == 'POST' and request.POST.get('action') == 'update':
        session = get_object_or_404(MentorEngagement, pk=request.POST.get('session_id'))
        new_status = request.POST.get('status', '')
        if new_status not in dict(MentorEngagement.STATUS_CHOICES):
            messages.error(request, 'Choose a valid session status.')
        else:
            old_status, old_date, old_start_time = session.status, session.date, session.start_time
            session.status = new_status
            session.outcome = request.POST.get('outcome', '').strip()
            try:
                session.full_clean()
                session.save(update_fields=['status', 'outcome', 'updated_at'])
                if (old_status, old_date, old_start_time) != (session.status, session.date, session.start_time):
                    MentorEngagementHistory.objects.create(
                        engagement=session,
                        old_status=old_status,
                        new_status=session.status,
                        old_date=old_date,
                        new_date=session.date,
                        old_start_time=old_start_time,
                        new_start_time=session.start_time,
                        changed_by=request.user,
                        note=session.outcome,
                    )
                messages.success(request, f'Session status updated to {session.get_status_display()}.')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
        return redirect(request.get_full_path())

    queryset = MentorEngagement.objects.filter(status__in=('scheduled', 'confirmed')).select_related(
        'mentor', 'startup', 'scheduled_by'
    ).order_by('date', 'start_time', 'mentor__name')
    today = timezone.localdate()
    window = request.GET.get('window', '')
    if window == 'upcoming':
        queryset = queryset.filter(date__gte=today)
    elif window == 'overdue':
        queryset = queryset.filter(date__lt=today)
    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(
            Q(mentor__name__icontains=search) | Q(startup__name__icontains=search)
            | Q(topics__icontains=search) | Q(meeting_location__icontains=search)
        )
    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_obj = Paginator(queryset, 20).get_page(request.GET.get('page'))
    return render(request, 'mentor_sessions.html', {
        'form': form,
        'page_obj': page_obj,
        'sessions': page_obj,
        'search': search,
        'window': window,
        'page_query': query_params.urlencode(),
        'upcoming_count': MentorEngagement.objects.filter(
            status__in=('scheduled', 'confirmed'), date__gte=today
        ).count(),
        'overdue_count': MentorEngagement.objects.filter(
            status__in=('scheduled', 'confirmed'), date__lt=today
        ).count(),
        'status_choices': MentorEngagement.STATUS_CHOICES,
        'recent_session_history': MentorEngagementHistory.objects.select_related(
            'engagement__mentor', 'engagement__startup', 'changed_by'
        )[:30],
    })


@staff_or_admin_required
@require_http_methods(['GET', 'POST'])
def participant_journey(request):
    selected_id = request.GET.get('participant') or request.POST.get('participant_id') or request.POST.get('journey_id')
    selected = ParticipantJourney.objects.filter(pk=selected_id).select_related('startup', 'assigned_to').first() if selected_id else None
    journey_form = ParticipantJourneyForm(instance=selected)
    support_form = ParticipantSupportForm()
    followup_form = ParticipantFollowUpForm(journey=selected)
    outcome_form = ParticipantOutcomeForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action in {'save_journey', 'new_journey'}:
            if action == 'save_journey' and selected is None:
                messages.error(request, 'Choose an existing participant journey to update.')
                return redirect('staff:participant_journey')
            instance = selected if action == 'save_journey' else ParticipantJourney()
            journey_form = ParticipantJourneyForm(request.POST, instance=instance)
            if journey_form.is_valid():
                before = (instance.current_stage, instance.status) if instance.pk else ('', '')
                journey = journey_form.save()
                stage, status = journey.current_stage, journey.status
                if before != (stage, status):
                    ParticipantJourneyHistory.objects.create(
                        journey=journey, old_stage=before[0], new_stage=stage,
                        old_status=before[1], new_status=status, changed_by=request.user,
                        note=journey_form.cleaned_data.get('change_note', '').strip()
                            or ('Journey created.' if not before[0] else 'Journey stage/status updated.'),
                    )
                messages.success(request, f'Journey record saved for {journey.participant_name}.')
                return redirect(f'{request.path}?participant={journey.pk}')
        elif selected and action == 'add_support':
            support_form = ParticipantSupportForm(request.POST)
            if support_form.is_valid():
                support = support_form.save(commit=False)
                support.journey, support.recorded_by = selected, request.user
                support.save()
                messages.success(request, 'Delivered support recorded.')
                return redirect(f'{request.path}?participant={selected.pk}')
        elif selected and action == 'add_followup':
            followup_form = ParticipantFollowUpForm(request.POST, journey=selected)
            if followup_form.is_valid():
                followup = followup_form.save(commit=False)
                followup.journey, followup.created_by = selected, request.user
                followup.full_clean()
                followup.save()
                ParticipantFollowUpHistory.objects.create(
                    follow_up=followup, new_status=followup.status, changed_by=request.user,
                    note='Follow-up action created.',
                )
                messages.success(request, 'Follow-up action added.')
                return redirect(f'{request.path}?participant={selected.pk}')
        elif selected and action == 'update_followup':
            item = get_object_or_404(ParticipantFollowUp, pk=request.POST.get('followup_id'), journey=selected)
            new_status = request.POST.get('status', '')
            if new_status in dict(ParticipantFollowUp.STATUS_CHOICES):
                old_status = item.status
                item.status = new_status
                item.save(update_fields=['status', 'updated_at'])
                if old_status != new_status:
                    ParticipantFollowUpHistory.objects.create(
                        follow_up=item, old_status=old_status, new_status=new_status,
                        changed_by=request.user, note=item.notes,
                    )
                messages.success(request, 'Follow-up status updated.')
            else:
                messages.error(request, 'Choose a valid follow-up status.')
            return redirect(f'{request.path}?participant={selected.pk}')
        elif selected and action == 'add_outcome':
            outcome_form = ParticipantOutcomeForm(request.POST)
            if outcome_form.is_valid():
                outcome = outcome_form.save(commit=False)
                outcome.journey, outcome.recorded_by = selected, request.user
                outcome.save()
                messages.success(request, 'Outcome snapshot recorded.')
                return redirect(f'{request.path}?participant={selected.pk}')
        else:
            messages.error(request, 'Choose a participant before recording support, follow-ups, or outcomes.')

    journeys = ParticipantJourney.objects.select_related('startup', 'assigned_to').all()
    search = request.GET.get('q', '').strip()
    stage_filter = request.GET.get('stage', '')
    status_filter = request.GET.get('status', '')
    if search:
        journeys = journeys.filter(
            Q(participant_name__icontains=search) | Q(email__icontains=search)
            | Q(startup__name__icontains=search) | Q(cohort__icontains=search)
        )
    if stage_filter in dict(ParticipantJourney.STAGE_CHOICES):
        journeys = journeys.filter(current_stage=stage_filter)
    if status_filter in dict(ParticipantJourney.STATUS_CHOICES):
        journeys = journeys.filter(status=status_filter)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_obj = Paginator(journeys, 20).get_page(request.GET.get('page'))

    return render(request, 'participant_journey.html', {
        'journeys': page_obj, 'page_obj': page_obj, 'page_query': query_params.urlencode(),
        'search': search, 'stage_filter': stage_filter, 'status_filter': status_filter,
        'stage_choices': ParticipantJourney.STAGE_CHOICES,
        'journey_status_choices': ParticipantJourney.STATUS_CHOICES,
        'followup_status_choices': ParticipantFollowUp.STATUS_CHOICES,
        'selected': selected, 'journey_form': journey_form,
        'support_form': support_form, 'followup_form': followup_form, 'outcome_form': outcome_form,
        'support_records': selected.support_deliveries.all()[:20] if selected else (),
        'followups': selected.follow_ups.select_related('assigned_to', 'mentor', 'mentor_session').all()[:30] if selected else (),
        'outcomes': selected.outcomes.select_related('recorded_by').all()[:12] if selected else (),
        'journey_history': selected.history.select_related('changed_by').all()[:20] if selected else (),
        'counts': {
            'active': ParticipantJourney.objects.filter(status='active').count(),
            'followups_due': ParticipantFollowUp.objects.filter(status__in=('open', 'in_progress'), due_date__lte=timezone.localdate()).count(),
            'support_this_month': ParticipantSupport.objects.filter(delivered_on__year=timezone.localdate().year, delivered_on__month=timezone.localdate().month).count(),
        },
    })


def _ical_escape(value):
    return str(value or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r', '').replace('\n', '\\n')


@staff_or_admin_required
def mentor_session_ical(request, pk):
    session = get_object_or_404(
        MentorEngagement.objects.select_related('mentor', 'startup'),
        pk=pk, status__in=('scheduled', 'confirmed'), start_time__isnull=False,
    )
    start = timezone.make_aware(datetime.combine(session.date, session.start_time))
    end = start + timedelta(hours=float(session.hours))
    event = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//DTBi BUNI//Mentor Session//EN',
        'BEGIN:VEVENT', f'UID:dtbi-mentor-session-{session.pk}@dtbisystem',
        f'DTSTAMP:{timezone.now().astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")}',
        f'DTSTART:{start.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")}',
        f'DTEND:{end.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")}',
        f'SUMMARY:{_ical_escape(f"Mentoring: {session.mentor.name} / {session.startup.name}")}',
        f'DESCRIPTION:{_ical_escape(session.topics)}',
        f'LOCATION:{_ical_escape(session.meeting_url or session.meeting_location)}',
        'END:VEVENT', 'END:VCALENDAR', '',
    ]
    response = HttpResponse('\r\n'.join(event), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="mentor-session-{session.pk}.ics"'
    return response


@require_http_methods(['GET', 'POST'])
def mentor_profile(request, pk):
    mentor = get_object_or_404(Mentor, pk=pk, is_active=True)
    if request.method == 'POST' and request.user.is_authenticated:
        if not (request.user.is_superuser or UserProfile.objects.filter(user=request.user, user_type__in=('admin', 'staff')).exists()):
            raise PermissionDenied
        form_data = request.POST
        try:
            session = MentorEngagement(
                mentor=mentor,
                startup=Startup.objects.get(pk=form_data.get('startup')),
                date=date.fromisoformat(form_data.get('date', '')),
                hours=form_data.get('hours') or 0,
                topics=form_data.get('topics', '').strip(),
                outcome=form_data.get('outcome', '').strip(),
            )
            if session.date > timezone.localdate():
                raise ValidationError('Use the session arrangements page to book a future date.')
            session.full_clean()
            session.save()
            MentorEngagementHistory.objects.create(
                engagement=session,
                old_status='',
                new_status=session.status,
                new_date=session.date,
                changed_by=request.user,
                note='Completed mentoring session recorded.',
            )
            messages.success(request, 'Mentor session saved.')
            return redirect('staff:mentor_profile', pk=mentor.pk)
        except (ValidationError, ValueError, Startup.DoesNotExist) as exc:
            message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Enter a valid startup, date, and hours.'
            messages.error(request, message)
    record_page_visit(request, 'mentor', mentor.pk, mentor.name)
    return render(request, 'mentor_profile.html', {
        'mentor': mentor,
        'startups': Startup.objects.filter(status='active').order_by('name'),
        'can_record_session': request.user.is_authenticated and (
            request.user.is_superuser or UserProfile.objects.filter(user=request.user, user_type__in=('admin', 'staff')).exists()
        ),
        'sessions': mentor.engagements.filter(status='completed').select_related('startup')[:20] if (
            request.user.is_authenticated and (
                request.user.is_superuser or UserProfile.objects.filter(user=request.user, user_type__in=('admin', 'staff')).exists()
            )
        ) else (),
        'scheduled_sessions': mentor.engagements.filter(status__in=('scheduled', 'confirmed')).select_related('startup').order_by('date', 'start_time')[:10] if (
            request.user.is_authenticated and (
                request.user.is_superuser or UserProfile.objects.filter(user=request.user, user_type__in=('admin', 'staff')).exists()
            )
        ) else (),
    })


def investor_profile(request, pk):
    investor = get_object_or_404(Investor, pk=pk, status='active')
    record_page_visit(request, 'investor', investor.pk, investor.organization or investor.name)
    return render(request, 'investor_profile.html', {
        'investor': investor,
        'fundings': investor.fundings.select_related('startup').order_by('-created_at')[:30],
    })
