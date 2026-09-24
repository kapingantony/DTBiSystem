import csv
import io
from datetime import date, datetime, timedelta
from functools import wraps
from html import escape
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook

from .data_services import (
    IMPORT_FIELDS, IMPORT_MODELS, analyze_import_preview, commit_import,
    preview_import, report_data,
)
from .models import DataImportBatch, Investor, Mentor, MentorEngagement, PageVisit, Startup, UserProfile
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
    return render(request, 'data_hub.html', {
        'recent_imports': DataImportBatch.objects.select_related('uploaded_by')[:8],
        'unread_visits': PageVisit.objects.filter(is_read=False).count(),
        'is_admin': request.user.is_superuser or UserProfile.objects.filter(user=request.user, user_type='admin').exists(),
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
    ]:
        summary.append([label, value])
    for currency, amount in sorted(data['funding_totals'].items()):
        summary.append([f'Funding recorded ({currency})', amount])
    summary.append(['Activity signal (rule based)', data['activity_signal']])
    summary.append(['Executive summary source', data['executive_summary_source']])
    summary.append(['Executive summary', data['executive_summary']])
    for title, headers, rows in [
        ('Startup status', ['Status', 'Current count'], [(r['status'], r['total']) for r in data['startups_by_status']]),
        ('Status history', ['Startup status', 'Contract status', 'Events'], [(r['status'], r['contract_status'], r['total']) for r in data['status_changes']]),
        ('Funding', ['Startup', 'Currency', 'Status', 'Investor', 'Source', 'Amount', 'Records'], [(r['startup__name'], r['currency'], r['status'], r['investor__name'] or '', r['source'], r['total_amount'], r['records']) for r in data['funding']]),
        ('Mentor sessions', ['Mentor', 'Startup', 'Date', 'Hours', 'Topics', 'Outcome'], [(r['mentor__name'], r['startup__name'], r['date'], r['hours'], r['topics'], r['outcome']) for r in data['mentor_rows']]),
        ('Page visits', ['Page type', 'Record', 'Unique daily visits'], [(r['page_type'], r['display_name'], r['visits']) for r in data['page_visits']]),
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
        ['KPI observations', str(data['kpi_observations'])], ['Tracked daily page visits', str(data['page_visit_total'])],
    ]
    summary.extend([[f'Funding recorded ({currency})', str(amount)] for currency, amount in sorted(data['funding_totals'].items())])
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
        ('Page visits', ['Record', 'Type', 'Unique daily visits'], [
            (row['display_name'], row['page_type'], str(row['visits'])) for row in data['page_visits']
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
    story.append(Paragraph('Counts reflect records and events currently recorded in the system. Historical status tracking and mentorship reporting begin when those features are introduced; this report does not infer earlier events. Funding totals retain the currency of each record and must be compared within currency.', styles['BodyText']))
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
    if page_type in {'startup', 'mentor', 'investor'}:
        visits = visits.filter(page_type=page_type)
    return render(request, 'page_visit_admin.html', {
        'visits': visits[:200],
        'unread_count': PageVisit.objects.filter(is_read=False).count(),
        'page_type': page_type,
    })


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
            session.full_clean()
            session.save()
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
        'sessions': mentor.engagements.select_related('startup')[:20] if (
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
