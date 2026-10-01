"""Public directory report downloads (CSV and PDF).

Anyone visiting the platform can download a report of the public startup,
mentor, and investor directories. The exported rows mirror exactly what a
visitor can already see on the corresponding directory page — no private
or internal fields are exposed.
"""
import csv
import io
import re
from datetime import datetime, timezone as dt_timezone
from html import escape as html_escape

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from .models import Investor, Mentor, Startup

REPORT_KINDS = ('startups', 'mentors', 'investors')

_WHITESPACE = re.compile(r'\s+')

_REPORT_META = {
    'startups': ('Startup directory', 'startup_directory'),
    'mentors': ('Mentor directory', 'mentor_directory'),
    'investors': ('Investor directory', 'investor_directory'),
}

_PDF_WEIGHTS = {
    'startups': [1.5, 0.9, 1.1, 2.4, 1.2, 1.4, 1.0, 0.9, 0.8],
    'mentors': [1.5, 1.1, 2.2, 2.1, 1.2, 1.5, 1.1, 0.9],
    'investors': [1.4, 1.3, 1.7, 1.1, 2.4, 1.4, 1.0, 0.9],
}


def _clean(value, limit=None):
    """Collapse newlines/whitespace so every cell is a single aligned line."""
    if value is None:
        return ''
    text = _WHITESPACE.sub(' ', str(value)).strip()
    if limit is not None and len(text) > limit:
        text = text[:max(limit - 3, 1)].rstrip() + '...'
    return text


def _startups_rows():
    queryset = Startup.objects.filter(directory_visible=True, status='active').order_by('name')
    headers = [
        'Name', 'Type', 'Industry', 'Description', 'Website', 'Contact email',
        'Source', 'Founded date', 'Profile completed (%)',
    ]
    rows = [
        [
            s.name,
            s.get_startup_type_display(),
            s.industry,
            s.description,
            s.website,
            s.contact_email,
            s.source,
            s.founded_date.isoformat() if s.founded_date else '',
            s.profile_completion,
        ]
        for s in queryset
    ]
    return headers, rows


def _mentors_rows():
    queryset = Mentor.objects.filter(is_active=True).order_by('name')
    headers = [
        'Name', 'Role', 'Skills', 'Training topics', 'Education level',
        'Email', 'Source', 'Member since',
    ]
    rows = [
        [
            m.name,
            m.role,
            m.skills,
            m.training_topics,
            m.education_level,
            m.email,
            m.source,
            m.created_at.date().isoformat() if m.created_at else '',
        ]
        for m in queryset
    ]
    return headers, rows


def _investors_rows():
    queryset = Investor.objects.filter(status='active').order_by('name')
    headers = [
        'Name', 'Organization', 'Investment interest', 'Website', 'Description',
        'Email', 'Source', 'Member since',
    ]
    rows = [
        [
            i.name,
            i.organization,
            i.investment_interest,
            i.website,
            i.description,
            i.email,
            i.source,
            i.created_at.date().isoformat() if i.created_at else '',
        ]
        for i in queryset
    ]
    return headers, rows


_BUILDERS = {
    'startups': _startups_rows,
    'mentors': _mentors_rows,
    'investors': _investors_rows,
}


def _report_parts(kind):
    if kind not in REPORT_KINDS:
        raise Http404
    title, filename_base = _REPORT_META[kind]
    headers, rows = _BUILDERS[kind]()
    return title, filename_base, headers, rows


@require_GET
def public_report_csv(request, kind):
    """Serve a public directory report as a well-structured CSV download."""
    title, filename_base, headers, rows = _report_parts(kind)

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\n')
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_clean(cell) for cell in row])

    # UTF-8 BOM keeps Excel/Sheets from mangling accented names.
    payload = '\ufeff' + buffer.getvalue()
    response = HttpResponse(payload, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
    response['X-Report-Title'] = title
    response['X-Report-Rows'] = str(len(rows))
    return response


def _build_pdf(kind, title, filename_base, headers, rows, row_count):
    def pdf_cell(value, style, limit=230):
        text = _clean(value, limit=limit)
        if not text:
            text = '-'
        text = html_escape(text)
        try:
            text.encode('latin-1')
        except UnicodeEncodeError:
            text = text.encode('latin-1', 'replace').decode('latin-1')
        return Paragraph(text, style)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:  # pragma: no cover - dependency declared in requirements.txt
        raise Http404 from exc

    output = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        output, pagesize=page,
        title=f'DTBi — {title}',
        leftMargin=30, rightMargin=30, topMargin=42, bottomMargin=40,
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('reportCell', parent=styles['BodyText'], fontSize=7.4, leading=9.2, spaceAfter=0)
    head_style = ParagraphStyle('reportHead', parent=styles['BodyText'], fontSize=7.6, leading=9.4,
                                textColor=colors.white, fontName='Helvetica-Bold', spaceAfter=0)
    generated = datetime.now(dt_timezone.utc).strftime('%d %b %Y, %H:%M UTC')

    story = [
        Paragraph(f'DTBi | BUNI — {html_escape(title)}', styles['Title']),
        Paragraph(
            f'Generated {generated} &nbsp;·&nbsp; {row_count} records &nbsp;·&nbsp; '
            'Public directory export — reflects what visitors can see on the website.',
            styles['Normal'],
        ),
        Spacer(1, 14),
    ]

    weights = _PDF_WEIGHTS[kind]
    usable = page[0] - 60
    total_weight = sum(weights)
    col_widths = [usable * w / total_weight for w in weights]

    data = [[Paragraph(html_escape(str(h)), head_style) for h in headers]]
    for row in rows:
        data.append([pdf_cell(cell, cell_style) for cell in row])

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#12304a')),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#ccd5df')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f8')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#5a6b7d'))
        canvas.drawString(30, 20, f'DTBi | BUNI — {title}')
        canvas.drawRightString(page[0] - 30, 20, f'Page {doc_.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue(), f'{filename_base}.pdf'


@require_GET
def public_report_pdf(request, kind):
    """Serve a public directory report as a printable PDF download."""
    title, filename_base, headers, rows = _report_parts(kind)
    # Materialize and clean once so the row count and the table always agree.
    cleaned = [[_clean(cell) for cell in row] for row in rows]
    payload, filename = _build_pdf(kind, title, filename_base, headers, cleaned, len(cleaned))
    response = HttpResponse(payload, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Report-Title'] = title
    response['X-Report-Rows'] = str(len(cleaned))
    return response
