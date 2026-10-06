import re
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.http import urlencode, url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.http import Http404, HttpResponse, JsonResponse

from .models import (
    Startup, Founder, Opportunity, Funding,
    KPI, PitchDeck, ServiceOffered, Partnership, PartnershipHistory,
    UserProfile, RegistrationRate, ProfileView, LoginNotification, SiteVisit, PageVisit,
    Mentor, Investor
)
from .forms import (
    StartupForm, StartupOwnerForm, FounderFormSet, OpportunityFormSet,
    FundingFormSet, KPIFormSet, PitchDeckFormSet,
    ServiceOfferedFormSet, PartnershipForm, AccountForm,
    ProfilePreferencesForm, MentorForm, InvestorForm, ManagedUserForm,
)
from .data_views import record_page_visit

User = get_user_model()

STARTUP_INDUSTRY_CATEGORIES = (
    ('agriculture', 'Agriculture & Agritech', ('agriculture', 'agri', 'agribusiness', 'farming', 'livestock')),
    ('biotechnology', 'Biotechnology & Life Sciences', ('biotech', 'biotechnology', 'life science', 'laboratory')),
    ('construction', 'Construction & Real Estate', ('construction', 'real estate', 'property', 'building')),
    ('creative', 'Creative Industries & Media', ('creative', 'media', 'film', 'design', 'animation', 'publishing')),
    ('education', 'Education & EdTech', ('education', 'edtech', 'edu-tech', 'e-learning', 'learning', 'training')),
    ('energy', 'Energy & Clean Technology', ('energy', 'renewable', 'solar', 'clean technology', 'cleantech')),
    ('finance', 'Financial Services & FinTech', ('financial', 'finance', 'fintech', 'banking', 'payments', 'insurance')),
    ('food', 'Food & Beverage', ('food', 'beverage', 'food processing')),
    ('health', 'Health & MedTech', ('health', 'medical', 'medtech', 'pharma', 'wellness')),
    ('ict', 'ICT & Software', ('ict', 'software', 'information technology', 'telecommunications', 'computer systems', 'cybersecurity')),
    ('manufacturing', 'Manufacturing & Industry', ('manufacturing', 'industrial', 'engineering', 'fabrication')),
    ('professional', 'Professional & Business Services', ('professional services', 'business services', 'consulting')),
    ('retail', 'Retail & E-commerce', ('retail', 'e-commerce', 'ecommerce', 'online marketplace')),
    ('social', 'Social Enterprise & Community Services', ('social enterprise', 'community services', 'non-profit', 'nonprofit')),
    ('tourism', 'Tourism & Hospitality', ('tourism', 'hospitality', 'travel', 'hotel')),
    ('transport', 'Transport & Logistics', ('transport', 'logistics', 'mobility', 'delivery')),
    ('water', 'Water & Sanitation', ('water', 'sanitation', 'waste management')),
)


def _sector_keyword_pattern(keyword):
    """Anchor a sector keyword to its left word edge only.

    Left edge, not both: `edtech` must not match "Health & MedTech" (embedded),
    while `agri` must still match "Agritech" (prefix).
    """
    return r'(?<![A-Za-z])' + re.escape(keyword)


def sector_query(sector):
    """Industry query matching one STARTUP_INDUSTRY_CATEGORIES entry."""
    query = Q()
    for keyword in sector[2]:
        query |= Q(industry__iregex=_sector_keyword_pattern(keyword))
    return query


def industry_matches_sector_keywords(industry_text, keywords):
    """True when `industry_text` contains a sector keyword at its left word edge."""
    return any(re.search(_sector_keyword_pattern(keyword), industry_text) for keyword in keywords)


def get_visitor_counts():
    now = timezone.localtime()
    today = now.date()
    month_start = today.replace(day=1)
    # Use the current calendar week, clipped to this month so week is a subset of month.
    week_start = max(today - timezone.timedelta(days=today.weekday()), month_start)
    return {
        'total': SiteVisit.objects.count(),
        'today': SiteVisit.objects.filter(last_seen__date=today).count(),
        'week': SiteVisit.objects.filter(last_seen__date__gte=week_start).count(),
        'month': SiteVisit.objects.filter(last_seen__date__gte=month_start).count(),
    }


def get_profile(user):
    """Return the user's profile, creating it when it does not exist yet."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _impact_period_options(current_year, available_years=()):
    """Build four-year blocks anchored on the startup portfolio's 2014 records."""
    anchor = 2014
    earlier_years = [year for year in available_years if year and year < anchor]
    if earlier_years:
        anchor -= ((anchor - min(earlier_years) + 3) // 4) * 4
    last_start = anchor + (max(0, current_year - anchor) // 4) * 4
    return [
        {'start': year, 'end': year + 3, 'key': f'{year}-{year + 3}', 'label': f'{year}–{year + 3}'}
        for year in range(anchor, last_start + 1, 4)
    ]


def _startup_industry_icon(industry):
    value = (industry or '').casefold()
    categories = (
        ('manufact', 'fa-industry'), ('fintech', 'fa-wallet'), ('e-commerce', 'fa-cart-shopping'),
        ('edutech', 'fa-graduation-cap'), ('tourism', 'fa-compass'), ('logistics', 'fa-truck-fast'),
        ('real estate', 'fa-city'), ('renewable', 'fa-solar-panel'), ('entertainment', 'fa-film'),
        ('health', 'fa-heart-pulse'), ('cyber', 'fa-shield-halved'),
    )
    return next((icon for keyword, icon in categories if keyword in value), 'fa-rocket')


def _illustrative_startup_metrics(startup):
    """Return stable illustrative metrics for presentation where the real record is absent."""
    identity = startup.slug or startup.name
    seed = sum((position + 1) * ord(character) for position, character in enumerate(identity.casefold()))
    participant_count = 4 + seed % 8
    return {
        'participant_journeys_started': participant_count,
        'support_activities': participant_count + 3 + seed % 9,
        'participants_supported': participant_count,
        'mentor_sessions': 2 + seed % 7,
        'participants_with_outcomes': max(2, participant_count - seed % 3),
        'outcome_snapshots': participant_count + seed % 4,
        'milestones': 1 + seed % 4,
        'full_time_jobs': 3 + seed % 24,
        'part_time_jobs': 1 + seed % 11,
    }


def _apply_illustrative_metrics(row, allow_without_cohort=False):
    """Fill absent activity groups with stable illustrative figures and mark their source."""
    if not row.get('cohort_year') and not allow_without_cohort:
        row['illustrative_groups'] = []
        row['data_basis'] = 'Recorded system data'
        return row
    illustrative = _illustrative_startup_metrics(row['startup'])
    presence = row.get('data_presence', {})
    groups = {
        'journeys': ('participant_journeys_started',),
        'support': ('support_activities', 'participants_supported'),
        'mentoring': ('mentor_sessions',),
        'outcomes': ('participants_with_outcomes', 'outcome_snapshots', 'milestones', 'full_time_jobs', 'part_time_jobs'),
    }
    illustrative_groups = []
    for group, fields in groups.items():
        if not presence.get(group):
            for field in fields:
                row[field] = illustrative[field]
            illustrative_groups.append(group)
    row['illustrative_groups'] = illustrative_groups
    row['includes_demo'] = bool(illustrative_groups)
    row['data_basis'] = 'Illustrative values' if len(illustrative_groups) == len(groups) else ('Recorded + illustrative' if illustrative_groups else 'Recorded system data')
    return row


def _summarize_startup_rows(rows):
    keys = (
        'participant_journeys_started', 'support_activities', 'participants_supported',
        'mentor_sessions', 'participants_with_outcomes', 'outcome_snapshots',
        'milestones', 'full_time_jobs', 'part_time_jobs',
    )
    result = {key: sum(row[key] for row in rows) for key in keys}
    result['published_startups'] = len(rows)
    result['illustrative_startups'] = sum(bool(row.get('includes_demo')) for row in rows)
    result['includes_demo'] = bool(result['illustrative_startups'])
    return result


def _startup_impact_rows(cohort_startups, start_year, end_year):
    """Aggregate recorded journey, support, mentoring and outcome data by startup."""
    from .models import ParticipantJourney, ParticipantOutcome, ParticipantSupport, MentorEngagement

    startup_list = list(cohort_startups)
    metric_keys = (
        'participant_journeys_started', 'support_activities', 'participants_supported',
        'mentor_sessions', 'participants_with_outcomes', 'outcome_snapshots',
        'milestones', 'full_time_jobs', 'part_time_jobs',
    )
    metrics = {item.pk: dict.fromkeys(metric_keys, 0) for item in startup_list}
    data_presence = {item.pk: {'journeys': False, 'support': False, 'mentoring': False, 'outcomes': False} for item in startup_list}
    startup_ids = list(metrics)
    if not startup_ids:
        return [], dict.fromkeys(metric_keys, 0)

    start_date = date(start_year, 1, 1)
    end_date = min(date(end_year, 12, 31), timezone.localdate())

    for row in ParticipantJourney.objects.filter(
        startup_id__in=startup_ids, started_on__range=(start_date, end_date)
    ).values('startup_id').annotate(total=Count('pk')):
        metrics[row['startup_id']]['participant_journeys_started'] = row['total']
        data_presence[row['startup_id']]['journeys'] = row['total'] > 0

    for row in ParticipantSupport.objects.filter(
        journey__startup_id__in=startup_ids,
        delivered_on__range=(start_date, end_date),
    ).values('journey__startup_id').annotate(
        activities=Count('pk'), people=Count('journey_id', distinct=True),
    ):
        metrics[row['journey__startup_id']]['support_activities'] = row['activities']
        metrics[row['journey__startup_id']]['participants_supported'] = row['people']
        data_presence[row['journey__startup_id']]['support'] = row['activities'] > 0

    for row in MentorEngagement.objects.filter(
        startup_id__in=startup_ids, date__range=(start_date, end_date), status='completed'
    ).values('startup_id').annotate(total=Count('pk')):
        metrics[row['startup_id']]['mentor_sessions'] = row['total']
        data_presence[row['startup_id']]['mentoring'] = row['total'] > 0

    outcomes = ParticipantOutcome.objects.filter(
        journey__startup_id__in=startup_ids,
        recorded_on__range=(start_date, end_date),
    ).select_related('journey').order_by('journey_id', '-recorded_on', '-created_at')
    latest_by_journey = {}
    people_by_startup = {}
    for outcome in outcomes:
        startup_id = outcome.journey.startup_id
        if startup_id is None:
            continue
        item_metrics = metrics[startup_id]
        item_metrics['outcome_snapshots'] += 1
        item_metrics['milestones'] += bool(outcome.milestone)
        data_presence[startup_id]['outcomes'] = True
        people_by_startup.setdefault(startup_id, set()).add(outcome.journey_id)
        latest_by_journey.setdefault(outcome.journey_id, outcome)
    for startup_id, journey_ids in people_by_startup.items():
        metrics[startup_id]['participants_with_outcomes'] = len(journey_ids)
    for outcome in latest_by_journey.values():
        startup_id = outcome.journey.startup_id
        metrics[startup_id]['full_time_jobs'] += outcome.full_time_jobs
        metrics[startup_id]['part_time_jobs'] += outcome.part_time_jobs

    rows = []
    for item in startup_list:
        cohort_year = item.year_incubated or (item.incubation_start.year if item.incubation_start else None) or (item.founded_date.year if item.founded_date else None)
        rows.append({'startup': item, 'cohort_year': cohort_year, 'data_presence': data_presence[item.pk], **metrics[item.pk]})
    summary = {key: sum(item[key] for item in metrics.values()) for key in metric_keys}
    return rows, summary


@login_required
@require_http_methods(['GET', 'POST'])
def settings_view(request):
    profile = get_profile(request.user)
    account_form = AccountForm(request.POST or None, instance=request.user)
    preferences_form = ProfilePreferencesForm(request.POST or None, instance=profile)
    if request.method == 'POST' and account_form.is_valid() and preferences_form.is_valid():
        account_form.save()
        preferences_form.save()
        messages.success(request, 'Your account preferences have been saved.')
        return redirect('staff:settings')
    return render(request, 'settings.html', {
        'account_form': account_form,
        'preferences_form': preferences_form,
        'profile': profile,
    })


def landing(request):
    """Public system overview with live platform statistics."""
    search_query = request.GET.get('q', '').strip()
    startup_results = Startup.objects.filter(status='active', directory_visible=True)
    if search_query:
        startup_results = startup_results.filter(
            Q(name__icontains=search_query)
            | Q(industry__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    system_stats = {
        'startups': Startup.objects.filter(status='active', directory_visible=True).count(),
        'mentors': Mentor.objects.filter(is_active=True).count(),
        'investors': Investor.objects.filter(status='active').count(),
        'founders': Founder.objects.count(),
        'opportunities': Opportunity.objects.count(),
        'funding_records': Funding.objects.filter(status__in=('received', 'committed')).count(),
    }
    upcoming_opportunities = Opportunity.objects.filter(
        status='open', startup__status='active', startup__directory_visible=True,
    ).filter(Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate())).select_related('startup').order_by('deadline', 'title')[:8]
    return render(request, 'landing.html', {
        'search_query': search_query,
        'startup_results': startup_results[:8],
        'visitor_counts': get_visitor_counts(),
        'system_stats': system_stats,
        'upcoming_opportunities': upcoming_opportunities,
    })


def impact_explorer(request):
    """Compare published startup cohorts and recorded outcomes in four-year periods."""
    current_year = timezone.localdate().year
    visible_startups = Startup.objects.filter(directory_visible=True, status='active').order_by('name')
    known_years = []
    for incubated, incubation_start, founded in visible_startups.values_list('year_incubated', 'incubation_start', 'founded_date'):
        year = incubated or (incubation_start.year if incubation_start else None) or (founded.year if founded else None)
        if year:
            known_years.append(year)
    periods = _impact_period_options(current_year, known_years)
    latest_data_year = max((year for year in known_years if year <= current_year), default=current_year)
    default_period = next((item for item in periods if item['start'] <= latest_data_year <= item['end']), periods[-1])
    period_key = request.GET.get('period', default_period['key'])
    period = next((item for item in periods if item['key'] == period_key), default_period)
    selected_startup = request.GET.get('startup', '').strip()

    cohort = visible_startups.filter(
        Q(year_incubated__range=(period['start'], period['end']))
        | Q(year_incubated__isnull=True, incubation_start__year__range=(period['start'], period['end']))
        | Q(year_incubated__isnull=True, incubation_start__isnull=True, founded_date__year__range=(period['start'], period['end']))
    )
    startup = None
    if selected_startup.isdigit():
        startup = cohort.filter(pk=selected_startup).first()
        if startup:
            cohort = cohort.filter(pk=startup.pk)
        else:
            selected_startup = ''
    else:
        selected_startup = ''

    startup_rows, _recorded_summary = _startup_impact_rows(cohort, period['start'], period['end'])
    startup_rows = [_apply_illustrative_metrics(row) for row in startup_rows]
    summary = _summarize_startup_rows(startup_rows)
    annual_rows = []
    for year in range(period['start'], min(period['end'], current_year) + 1):
        annual_startups, _annual_recorded = _startup_impact_rows(cohort, year, year)
        annual_by_id = {row['startup'].pk: row for row in annual_startups}
        effective_annual = []
        for full_row in startup_rows:
            year_row = annual_by_id.get(full_row['startup'].pk)
            if year_row is None:
                continue
            # Illustrative figures belong to the cohort year only; recorded annual activity stays as recorded.
            for group in full_row.get('illustrative_groups', []):
                if full_row.get('cohort_year') == year:
                    illustrative_values = _illustrative_startup_metrics(full_row['startup'])
                    fields = {
                        'journeys': ('participant_journeys_started',),
                        'support': ('support_activities', 'participants_supported'),
                        'mentoring': ('mentor_sessions',),
                        'outcomes': ('participants_with_outcomes', 'outcome_snapshots', 'milestones', 'full_time_jobs', 'part_time_jobs'),
                    }[group]
                    for field in fields:
                        year_row[field] = illustrative_values[field]
            year_row['includes_demo'] = bool(full_row.get('illustrative_groups') and full_row.get('cohort_year') == year)
            effective_annual.append(year_row)
        annual = _summarize_startup_rows(effective_annual)
        annual_rows.append({'year': year, 'published_startups': sum(row.get('cohort_year') == year for row in startup_rows), **annual})

    if request.GET.get('format') in {'xlsx', 'pdf'}:
        from .impact_reports import startup_impact_pdf, startup_impact_xlsx
        period_label = period['label']
        as_of_label = timezone.localdate().strftime('%d %b %Y')
        if request.GET.get('format') == 'xlsx':
            payload = startup_impact_xlsx(period_label, summary, annual_rows, startup_rows, as_of_label)
            response = HttpResponse(payload, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="dtbi-startup-impact-{period["start"]}-{period["end"]}.xlsx"'
            return response
        try:
            payload = startup_impact_pdf(period_label, summary, annual_rows, startup_rows, as_of_label)
        except RuntimeError as exc:
            messages.error(request, str(exc))
            return redirect(f"{request.path}?period={period['key']}")
        response = HttpResponse(payload, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="dtbi-startup-impact-{period["start"]}-{period["end"]}.pdf"'
        return response

    max_jobs = max((row['full_time_jobs'] + row['part_time_jobs'] for row in startup_rows), default=0)
    for row in startup_rows:
        row['jobs_total'] = row['full_time_jobs'] + row['part_time_jobs']
        row['jobs_bar_width'] = round((row['jobs_total'] / max_jobs) * 100) if max_jobs else 0
    annual_chart_max = max((max(row['participant_journeys_started'], row['support_activities'], row['mentor_sessions'], row['participants_with_outcomes']) for row in annual_rows), default=0)
    for row in annual_rows:
        row['chart_journeys_width'] = round(row['participant_journeys_started'] * 100 / annual_chart_max) if annual_chart_max else 0
        row['chart_support_width'] = round(row['support_activities'] * 100 / annual_chart_max) if annual_chart_max else 0
        row['chart_sessions_width'] = round(row['mentor_sessions'] * 100 / annual_chart_max) if annual_chart_max else 0
        row['chart_outcomes_width'] = round(row['participants_with_outcomes'] * 100 / annual_chart_max) if annual_chart_max else 0
    employment_total = summary['full_time_jobs'] + summary['part_time_jobs']
    full_time_share = round(summary['full_time_jobs'] * 100 / employment_total, 1) if employment_total else 0
    part_time_share = round(summary['part_time_jobs'] * 100 / employment_total, 1) if employment_total else 0
    return render(request, 'impact_explorer.html', {
        'periods': periods, 'selected_period': period['key'], 'period_label': period['label'],
        'startups': cohort, 'selected_startup': str(startup.pk) if startup else '',
        'startup': startup, 'startup_count': summary['published_startups'],
        'participant_count': summary['participant_journeys_started'],
        'support_count': summary['support_activities'], 'supported_count': summary['participants_supported'],
        'jobs_full': summary['full_time_jobs'], 'jobs_part': summary['part_time_jobs'],
        'sessions_count': summary['mentor_sessions'], 'outcome_count': summary['participants_with_outcomes'],
        'outcome_snapshots': summary['outcome_snapshots'], 'startup_rows': startup_rows,
        'annual_rows': annual_rows, 'summary': summary, 'jobs_chart_max': max_jobs,
        'employment_total': employment_total, 'full_time_share': full_time_share,
        'part_time_share': part_time_share,
    })


def hub_history(request):
    """Public history and archival photos from the tracer study."""
    early_history_photos = [
        {'image': 'img/history/early-days-01.jpg', 'alt': 'Early 3D printers and prototyping equipment in a makerspace', 'caption': 'Early makerspace equipment and prototypes', 'page': 13},
        {'image': 'img/history/early-days-02.jpg', 'alt': 'Participants working together around a business model worksheet', 'caption': 'Participants developing ideas together', 'page': 13},
        {'image': 'img/history/early-days-03.jpg', 'alt': 'A speaker sharing ideas with workshop participants', 'caption': 'A BUNI community workshop', 'page': 13},
        {'image': 'img/history/early-days-04.jpg', 'alt': 'Two members of the BUNI community wearing BUNI shirts', 'caption': 'BUNI community members', 'page': 13},
        {'image': 'img/history/early-days-05.jpg', 'alt': 'Audience attending an early BUNI community session', 'caption': 'A community learning session', 'page': 13},
        {'image': 'img/history/early-days-06.jpg', 'alt': 'A group of BUNI community members inside the hub', 'caption': 'The BUNI community at the hub', 'page': 13},
        {'image': 'img/history/early-days-07.jpg', 'alt': 'Two participants reviewing work at a laptop in a makerspace', 'caption': 'Working together on a digital product', 'page': 14},
        {'image': 'img/history/early-days-08.jpg', 'alt': 'A BUNI member presenting beside a BUNI Innovation Hub display', 'caption': 'Sharing the BUNI Innovation Hub story', 'page': 14},
        {'image': 'img/history/early-days-09.jpg', 'alt': 'TechBox team members at an innovation event', 'caption': 'A TechBox team moment', 'page': 14},
        {'image': 'img/history/early-days-10.jpg', 'alt': 'Audience seated at an innovation community event', 'caption': 'An innovation community gathering', 'page': 14},
        {'image': 'img/history/early-days-11.jpg', 'alt': 'Panel discussion with hub community members and partners', 'caption': 'A discussion with hub partners', 'page': 14},
        {'image': 'img/history/early-days-12.jpg', 'alt': 'A visitor meeting members of the startup community', 'caption': 'Visitors meeting startup teams', 'page': 14},
    ]
    return render(request, 'hub_history.html', {'early_history_photos': early_history_photos})


def visitor_stats(request):
    """Return current visitor totals for the live overview counter."""
    return JsonResponse(get_visitor_counts())


@login_required
def index(request):
    startups = Startup.objects.all()[:5]
    # Get registration rates
    rates = RegistrationRate.objects.all()
    profile = get_profile(request.user)
    context = {
        'startups': startups,
        'rates': rates,
        'profile': profile,
        'my_startup': profile.startup,
    }
    return render(request, 'index.html', context)


def startups(request):
    startup_list = Startup.objects.filter(directory_visible=True).prefetch_related('founders').annotate(
        participant_journey_count=Count('participant_journeys', distinct=True),
        support_activity_count=Count('participant_journeys__support_deliveries', distinct=True),
        completed_mentor_count=Count('mentor_engagements', filter=Q(mentor_engagements__status='completed'), distinct=True),
        participant_outcome_count=Count('participant_journeys__outcomes', distinct=True),
    )
    is_admin = request.user.is_authenticated and (request.user.is_superuser or get_profile(request.user).is_admin)
    if not is_admin:
        startup_list = startup_list.filter(status='active')
    startup_list = startup_list.order_by('industry', 'name')
    # Filter by type if specified
    startup_type = request.GET.get('type', '').strip().lower()
    if startup_type in {'public', 'individual'}:
        startup_list = startup_list.filter(startup_type=startup_type)
    search_query = request.GET.get('q', '').strip()
    industry_filter = request.GET.get('industry', '').strip()
    status_filter = request.GET.get('status', '').strip().lower()
    if search_query:
        startup_list = startup_list.filter(
            Q(name__icontains=search_query) | Q(industry__icontains=search_query)
            | Q(description__icontains=search_query) | Q(source__icontains=search_query)
        )
    if industry_filter.startswith('sector:'):
        sector_key = industry_filter.split(':', 1)[1]
        sector = next((item for item in STARTUP_INDUSTRY_CATEGORIES if item[0] == sector_key), None)
        if sector:
            startup_list = startup_list.filter(sector_query(sector))
        else:
            industry_filter = ''
    elif industry_filter:
        raw_industry = industry_filter.split(':', 1)[1] if industry_filter.startswith('industry:') else industry_filter
        startup_list = startup_list.filter(industry__iexact=raw_industry)
    if status_filter in dict(Startup.STATUS_CHOICES):
        startup_list = startup_list.filter(status=status_filter)
    industries = list(Startup.objects.filter(directory_visible=True).exclude(industry='').values_list('industry', flat=True).distinct().order_by('industry'))
    industry_options = [
        {'value': f'sector:{key}', 'label': label}
        for key, label, _keywords in STARTUP_INDUSTRY_CATEGORIES
    ]
    for industry in industries:
        industry_lower = industry.casefold()
        if not any(
            industry_matches_sector_keywords(industry_lower, keywords)
            for _key, _label, keywords in STARTUP_INDUSTRY_CATEGORIES
        ):
            industry_options.append({'value': f'industry:{industry}', 'label': industry})
    query_params = request.GET.copy()
    query_params.pop('page', None)
    showcase = list(startup_list[:8])
    page_obj = Paginator(startup_list, 25).get_page(request.GET.get('page'))
    for item in page_obj.object_list:
        item.industry_icon = _startup_industry_icon(item.industry)
        illustrative = _illustrative_startup_metrics(item)
        for field, real_field in (
            ('display_journeys', 'participant_journey_count'),
            ('display_support', 'support_activity_count'),
            ('display_sessions', 'completed_mentor_count'),
            ('display_outcomes', 'participant_outcome_count'),
        ):
            actual = getattr(item, real_field)
            setattr(item, field, actual or illustrative[{
                'display_journeys': 'participant_journeys_started',
                'display_support': 'support_activities',
                'display_sessions': 'mentor_sessions',
                'display_outcomes': 'participants_with_outcomes',
            }[field]])
            setattr(item, field + '_illustrative', not bool(actual))
    current_year = timezone.localdate().year
    impact_startups = Startup.objects.filter(directory_visible=True, status='active').order_by('name')
    known_years = []
    for incubated, incubation_start, founded in impact_startups.values_list('year_incubated', 'incubation_start', 'founded_date'):
        year = incubated or (incubation_start.year if incubation_start else None) or (founded.year if founded else None)
        if year:
            known_years.append(year)
    impact_periods = _impact_period_options(current_year, known_years)
    latest_data_year = max((year for year in known_years if year <= current_year), default=current_year)
    current_period = next((item for item in impact_periods if item['start'] <= latest_data_year <= item['end']), impact_periods[-1])
    context = {
        'startup_list': page_obj,
        'impact_periods': impact_periods,
        'impact_default_period': current_period['key'],
        'impact_startups': impact_startups,
        'page_obj': page_obj,
        'showcase': showcase,
        'filter_type': startup_type or '',
        'search_query': search_query,
        'industry_filter': industry_filter,
        'status_filter': status_filter,
        'industries': industry_options,
        'status_choices': Startup.STATUS_CHOICES,
        'page_query': query_params.urlencode(),
    }
    return render(request, 'startups.html', context)


@require_http_methods(["GET", "POST"])
def user_login(request):
    """Handle login according to the stored user role and Django permission flags."""
    if request.method == 'POST':
        login_identifier = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''

        user = authenticate(request, username=login_identifier, password=password)
        if user is None and '@' in login_identifier:
            matching_accounts = User.objects.filter(email__iexact=login_identifier)
            if matching_accounts.count() == 1:
                user = authenticate(request, username=matching_accounts.first().username, password=password)
        if user is None:
            messages.error(request, 'Invalid username/email or password, or this account is disabled.')
            return render(request, 'registration/login.html')

        profile, _ = UserProfile.objects.get_or_create(user=user)

        if user.is_superuser and profile.user_type != 'admin':
            profile.user_type = 'admin'
            profile.save(update_fields=['user_type'])
        elif user.is_staff and profile.user_type not in ('admin', 'staff'):
            profile.user_type = 'staff'
            profile.save(update_fields=['user_type'])

        login(request, user)
        profile.login_count += 1
        profile.last_login_ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        profile.save(update_fields=['login_count', 'last_login_ip'])

        next_url = request.POST.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)

        if profile.user_type == 'admin':
            return redirect('staff:dashboard')
        if profile.user_type == 'staff':
            return redirect('staff:dashboard')
        if profile.user_type == 'mentor' and hasattr(user, 'mentor_record'):
            return redirect('mentor_profile', pk=user.mentor_record.pk)
        if profile.user_type == 'investor' and hasattr(user, 'investor_record'):
            return redirect('investor_profile', pk=user.investor_record.pk)
        if profile.is_startup:
            return redirect('staff:startup_profile', slug=profile.startup.slug) if profile.startup else redirect('staff:startup_create')
        return redirect('staff:dashboard')

    return render(request, 'registration/login.html')


@require_http_methods(["GET", "POST"])
def user_logout(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('landing')


@login_required
def dashboard(request):
    """Dashboard view for authenticated users"""
    profile = get_profile(request.user)
    context = {
        'profile': profile,
        'user_type': profile.user_type,
    }

    if profile.is_admin:
        # Admin dashboard - show stats
        startups_count = Startup.objects.count()
        total_registrations = sum(r.total_registrations for r in RegistrationRate.objects.all())
        # Get recent login notifications
        recent_logins = LoginNotification.objects.order_by('-timestamp')[:5]
        context.update({
            'startups_count': startups_count,
            'total_registrations': total_registrations,
            'recent_logins': recent_logins,
            'dashboard_counts': {
                'active_startups': Startup.objects.filter(status='active', directory_visible=True).count(),
                'pending_startups': Startup.objects.filter(status='pending').count(),
                'mentors': Mentor.objects.filter(is_active=True).count(),
                'mentors_demo': Mentor.objects.filter(is_active=True).count() > 0 and not Mentor.objects.filter(is_active=True).exclude(source__startswith='DEMO ONLY').exists(),
                'investors': Investor.objects.filter(status='active').count(),
                'investors_demo': Investor.objects.filter(status='active').count() > 0 and not Investor.objects.filter(status='active').exclude(source__startswith='DEMO ONLY').exists(),
            },
        })
    elif profile.user_type == 'staff':
        from .models import MentorEngagement, ParticipantFollowUp, ParticipantJourney, Partnership
        context.update({
            'staff_operations': {
                'assigned_journeys': ParticipantJourney.objects.filter(assigned_to=request.user).count(),
                'followups_due': ParticipantFollowUp.objects.filter(
                    assigned_to=request.user, status__in=('open', 'in_progress'),
                    due_date__lte=timezone.localdate(),
                ).count(),
                'assigned_partnerships': Partnership.objects.filter(
                    assigned_to=request.user, status__in=('pending', 'under_review', 'in_progress'),
                ).count(),
                'upcoming_sessions': MentorEngagement.objects.filter(
                    scheduled_by=request.user, status__in=('scheduled', 'confirmed'), date__gte=timezone.localdate(),
                ).count(),
            },
        })
    elif profile.is_startup:
        # Startup owner dashboard
        startup = profile.startup
        if startup:
            context.update({
                'startup': startup,
                'profile_completion': startup.profile_completion,
                'total_funding': sum(f.amount for f in startup.fundings.all()),
                'kpi_count': startup.kpis.count(),
                'opportunity_count': startup.opportunities.count(),
            })
    elif profile.user_type == 'mentor' and hasattr(request.user, 'mentor_record'):
        mentor = request.user.mentor_record
        context.update({'mentor': mentor, 'my_sessions': mentor.engagements.select_related('startup').order_by('-date')[:10]})
    elif profile.user_type == 'investor' and hasattr(request.user, 'investor_record'):
        investor = request.user.investor_record
        context.update({'investor': investor, 'my_fundings': investor.fundings.select_related('startup').order_by('-created_at')[:10]})

    return render(request, 'dashboard.html', context)


@login_required
def profile_view_notification(request, user_id):
    """Show profile view notifications to the user"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    viewed_user = get_object_or_404(User, id=user_id)
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    # Track the profile view
    ProfileView.objects.get_or_create(
        viewer=request.user,
        viewed_profile_owner=viewed_user,
        startup=profile.startup,
    )

    # Get recent views
    recent_views = ProfileView.objects.filter(
        viewed_profile_owner=viewed_user
    ).order_by('-viewed_at')[:10]

    context = {
        'viewed_user': viewed_user,
        'recent_views': recent_views,
        'profile': profile,
    }
    return render(request, 'profile_views.html', context)


@require_http_methods(["GET", "POST"])
def register(request):
    """Handle startup-user registration only. Staff/admin accounts are created by administrators."""
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password = (request.POST.get('password') or '').strip()
        user_type = request.POST.get('user_type', 'public')

        if user_type not in ('public', 'individual'):
            messages.error(request, 'Public signup is only for startup accounts. Please choose Public Startup or Individual Startup.')
            return render(request, 'registration/register.html', {'user_types': [('public', 'Public Startup'), ('individual', 'Individual Startup')]})

        if not username or not password:
            messages.error(request, 'Username and password are required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=False,
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.user_type = user_type
            profile.save(update_fields=['user_type'])
            messages.success(request, 'Account created successfully. Please log in with your startup role.')
            return redirect('staff:user_login')

    user_types = [c for c in UserProfile.USER_TYPE_CHOICES if c[0] in ('public', 'individual')]
    return render(request, 'registration/register.html', {'user_types': user_types})


@login_required
@require_http_methods(["GET", "POST"])
def startup_create(request):
    """Create a new startup profile owned by the logged-in user"""
    profile = get_profile(request.user)

    # One startup per account — send the owner to the one they already have.
    if profile.startup:
        messages.info(request, 'You already added a startup. Here it is.')
        return redirect('staff:startup_profile', slug=profile.startup.slug)

    if request.method == 'POST':
        form = StartupOwnerForm(request.POST, request.FILES)
        founder_formset = FounderFormSet(request.POST, request.FILES, prefix='founders')
        opportunity_formset = OpportunityFormSet(request.POST, prefix='opportunities')
        funding_formset = FundingFormSet(request.POST, prefix='fundings')
        kpi_formset = KPIFormSet(request.POST, prefix='kpis')
        pitch_formset = PitchDeckFormSet(request.POST, request.FILES, prefix='pitches')
        service_formset = ServiceOfferedFormSet(request.POST, prefix='services')

        if (form.is_valid() and founder_formset.is_valid() and opportunity_formset.is_valid()
                and funding_formset.is_valid() and kpi_formset.is_valid()
                and pitch_formset.is_valid() and service_formset.is_valid()):
            with transaction.atomic():
                startup = form.save(commit=False)
                startup.startup_type = profile.user_type if profile.user_type in ('public', 'individual') else 'individual'
                startup.status = 'pending' if startup.startup_type == 'individual' else 'active'
                startup.save()
                founder_formset.instance = startup
                opportunity_formset.instance = startup
                funding_formset.instance = startup
                kpi_formset.instance = startup
                pitch_formset.instance = startup
                service_formset.instance = startup

                founder_formset.save()
                opportunity_formset.save()
                funding_formset.save()
                kpi_formset.save()
                pitch_formset.save()
                service_formset.save()

                startup.profile_completion = startup.calc_profile_completion()
                startup.save(update_fields=['profile_completion'])

                # Link the startup to the account that created it
                profile.startup = startup
                profile.save(update_fields=['startup'])

            messages.success(request, f'{startup.name} has been added to the platform.')
            return redirect('staff:startup_profile', slug=startup.slug)
    else:
        form = StartupOwnerForm()
        founder_formset = FounderFormSet(prefix='founders')
        opportunity_formset = OpportunityFormSet(prefix='opportunities')
        funding_formset = FundingFormSet(prefix='fundings')
        kpi_formset = KPIFormSet(prefix='kpis')
        pitch_formset = PitchDeckFormSet(prefix='pitches')
        service_formset = ServiceOfferedFormSet(prefix='services')

        # Suggest the account owner as the first founder
        founder_formset.forms[0].initial = {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
        }

    context = {
        'form': form,
        'founder_formset': founder_formset,
        'opportunity_formset': opportunity_formset,
        'funding_formset': funding_formset,
        'kpi_formset': kpi_formset,
        'pitch_formset': pitch_formset,
        'service_formset': service_formset,
        'creating': True,
        'can_edit': True,
        'show_admin_fields': False,
    }
    return render(request, 'startup_profile.html', context)


def _startup_lifecycle_data(startup):
    from django.db.models.functions import ExtractYear
    from .models import MentorEngagement, ParticipantJourney, ParticipantOutcome, ParticipantSupport

    current_year = timezone.localdate().year
    lifecycle_rows, lifetime = _startup_impact_rows([startup], 1900, current_year)
    lifecycle_row = lifecycle_rows[0]
    lifecycle_row['cohort_year'] = startup.year_incubated or (startup.incubation_start.year if startup.incubation_start else None) or (startup.founded_date.year if startup.founded_date else None)
    lifecycle_row = _apply_illustrative_metrics(lifecycle_row, allow_without_cohort=True)
    achievements = [
        {'icon': 'fa-route', 'label': 'Participant journeys', 'value': lifecycle_row['participant_journeys_started'], 'illustrative': 'journeys' in lifecycle_row['illustrative_groups']},
        {'icon': 'fa-hand-holding-heart', 'label': 'Support activities', 'value': lifecycle_row['support_activities'], 'illustrative': 'support' in lifecycle_row['illustrative_groups']},
        {'icon': 'fa-chalkboard-user', 'label': 'Completed mentor sessions', 'value': lifecycle_row['mentor_sessions'], 'illustrative': 'mentoring' in lifecycle_row['illustrative_groups']},
        {'icon': 'fa-chart-line', 'label': 'Participant outcomes', 'value': lifecycle_row['participants_with_outcomes'], 'illustrative': 'outcomes' in lifecycle_row['illustrative_groups']},
        {'icon': 'fa-people-group', 'label': 'Reported full-time jobs', 'value': lifecycle_row['full_time_jobs'], 'illustrative': 'outcomes' in lifecycle_row['illustrative_groups']},
        {'icon': 'fa-user-group', 'label': 'Reported part-time jobs', 'value': lifecycle_row['part_time_jobs'], 'illustrative': 'outcomes' in lifecycle_row['illustrative_groups']},
    ]
    timeline = []
    if startup.founded_date:
        timeline.append({'year': startup.founded_date.year, 'date': startup.founded_date, 'title': 'Founded', 'detail': startup.founded_date.strftime('%d %b %Y'), 'icon': 'fa-flag'})
    if startup.year_incubated:
        timeline.append({'year': startup.year_incubated, 'date': date(startup.year_incubated, 1, 1), 'title': 'DTBi cohort', 'detail': f'Cohort year {startup.year_incubated}', 'icon': 'fa-layer-group'})
    if startup.incubation_start:
        timeline.append({'year': startup.incubation_start.year, 'date': startup.incubation_start, 'title': 'Incubation started', 'detail': startup.incubation_start.strftime('%d %b %Y'), 'icon': 'fa-play'})
    if startup.incubation_end:
        timeline.append({'year': startup.incubation_end.year, 'date': startup.incubation_end, 'title': 'Incubation ended', 'detail': startup.incubation_end.strftime('%d %b %Y'), 'icon': 'fa-check'})
    if not startup.founded_date:
        timeline.append({'year': startup.year_incubated or current_year - 2, 'date': date(startup.year_incubated or current_year - 2, 1, 1), 'title': 'Founded' , 'detail': 'Date to confirm with the organization', 'icon': 'fa-flag', 'illustrative': True})
    if not startup.incubation_start:
        illustrative_year = startup.year_incubated or current_year - 2
        timeline.append({'year': illustrative_year, 'date': date(illustrative_year, 2, 1), 'title': 'Incubation start' , 'detail': 'Date to confirm with programme records', 'icon': 'fa-play', 'illustrative': True})
    if not startup.incubation_end:
        illustrative_year = (startup.year_incubated or current_year - 2) + 1
        timeline.append({'year': illustrative_year, 'date': date(illustrative_year, 12, 31), 'title': 'Incubation end' , 'detail': 'Date to confirm with programme records', 'icon': 'fa-check', 'illustrative': True})

    years = {}
    support_by_year = ParticipantSupport.objects.filter(journey__startup=startup).annotate(year=ExtractYear('delivered_on')).values('year').annotate(total=Count('pk'))
    for item in support_by_year:
        years.setdefault(item['year'], {})['support'] = item['total']
    sessions_by_year = MentorEngagement.objects.filter(startup=startup, status='completed').annotate(year=ExtractYear('date')).values('year').annotate(total=Count('pk'))
    for item in sessions_by_year:
        years.setdefault(item['year'], {})['sessions'] = item['total']
    outcomes_by_year = ParticipantOutcome.objects.filter(journey__startup=startup).annotate(year=ExtractYear('recorded_on')).values('year').annotate(total=Count('pk'))
    for item in outcomes_by_year:
        years.setdefault(item['year'], {})['outcomes'] = item['total']
    for year, values in years.items():
        detail = []
        if values.get('support'):
            detail.append(f"{values['support']} support activities")
        if values.get('sessions'):
            detail.append(f"{values['sessions']} completed mentor sessions")
        if values.get('outcomes'):
            detail.append(f"{values['outcomes']} outcome records")
        timeline.append({'year': year, 'date': date(year, 1, 1), 'title': f'Programme activity · {year}', 'detail': ' · '.join(detail), 'icon': 'fa-chart-column'})
    timeline.sort(key=lambda item: (item['date'], item['title']))
    return achievements, timeline



def _startup_profile_demo_data(startup):
    """Build display-only example values for blank profile panels; never persist them."""
    from types import SimpleNamespace

    seed = _illustrative_startup_metrics(startup)['participant_journeys_started']
    industry = startup.industry or 'Innovation and technology'
    year = startup.year_incubated or (startup.incubation_start.year if startup.incubation_start else None) or (startup.founded_date.year if startup.founded_date else timezone.localdate().year - 2)
    founders = list(startup.founders.all()) or [SimpleNamespace(
        name=f'{startup.name} Demo Founder', get_role_display=lambda: 'Founder',
        bio='Founder profile and organization leadership.',
        email=f'founder+{startup.slug}@example.test', linkedin='', twitter='', is_illustrative=True,
    )]
    opportunities = list(startup.opportunities.all()) or [SimpleNamespace(
        get_opportunity_type_display=lambda: 'Acceleration', status='open', get_status_display=lambda: 'Open',
        title='Growth opportunity',
        description='Explore upcoming opportunities in the ecosystem and find the right fit for your organization.',
        deadline=timezone.localdate() + timezone.timedelta(days=90), is_illustrative=True,
    )]
    fundings = list(startup.fundings.all()) or [SimpleNamespace(
        source='Investment fund', amount=25000 + seed * 500, get_funding_type_display=lambda: 'Seed',
        status='received', get_status_display=lambda: 'Received', date_received=timezone.localdate().replace(day=1), is_illustrative=True,
    )]
    kpis = list(startup.kpis.all()) or [SimpleNamespace(
        metric_name='Customers reached', metric_value=seed * 18, unit='people',
        target_value=seed * 25, achievement_pct=round(seed * 18 / (seed * 25) * 100),
        get_period_display=lambda: 'Annual measure', is_illustrative=True,
    )]
    pitch_decks = list(startup.pitch_decks.all()) or [SimpleNamespace(
        title=f'{startup.name} organization overview', description='Organization presentation summary.',
        presentation_date=date(year, 1, 1), file=None, is_illustrative=True,
    )]
    services = list(startup.services.all()) or [SimpleNamespace(
        get_category_display=lambda: industry, name=f'{industry} solutions',
        description='Services supporting this organization.', is_illustrative=True,
    )]
    demo_fields = {
        'industry': industry,
        'website': startup.website or f'https://example.org/ventures/{startup.slug}',
        'founded_year': startup.founded_date.year if startup.founded_date else year,
        'contact_email': startup.contact_email or f'hello+{startup.slug}@example.test',
        'phone': startup.phone or '+255 700 000 000',
        'year_incubated': year,
        'source': startup.source or 'DTBi portfolio',
        'incubation_start': startup.incubation_start or date(year, 1, 1),
        'incubation_end': startup.incubation_end or date(year + 1, 12, 31),
    }
    return {
        'profile_founders': founders, 'profile_opportunities': opportunities,
        'profile_fundings': fundings, 'profile_kpis': kpis,
        'profile_pitch_decks': pitch_decks, 'profile_services': services,
        'profile_demo': any(getattr(items[0], 'is_illustrative', False) for items in (founders, opportunities, fundings, kpis, pitch_decks, services)),
        'demo_fields': demo_fields,
        'display_funding_total': sum(item.amount for item in startup.fundings.all()) if startup.fundings.exists() else fundings[0].amount,
        'display_funding_count': startup.fundings.count() or 1,
    }

def startup_profile(request, slug):
    """Display public startup details and keep editing behind authentication."""
    startup = get_object_or_404(Startup, slug=slug)
    authenticated = request.user.is_authenticated
    if request.method == 'GET':
        record_page_visit(request, 'startup', startup.slug, startup.name)
    if not authenticated and (startup.status != 'active' or not startup.directory_visible):
        raise Http404
    profile = get_profile(request.user) if authenticated else None
    more_login_url = f"{reverse('staff:user_login')}?{urlencode({'next': request.get_full_path()})}"
    if request.method == 'POST' and not authenticated:
        return redirect(more_login_url)

    # Only the owner of the startup (or a hub admin) may change it.
    can_edit = bool(profile and (profile.is_admin or request.user.is_staff or profile.startup_id == startup.id))
    can_view_private = can_edit
    if startup.status == 'pending' and not can_edit:
        return redirect(f"{reverse('staff:user_login')}?next={request.get_full_path()}")
    can_view_mentor_sessions = bool(profile and (profile.is_admin or profile.is_staff_role or profile.startup_id == startup.id))

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'You can only edit your own startup profile.')
            return redirect('staff:startup_profile', slug=startup.slug)

        form_class = StartupForm if profile.is_admin else StartupOwnerForm
        form = form_class(request.POST, request.FILES, instance=startup)
        founder_formset = FounderFormSet(request.POST, request.FILES, instance=startup, prefix='founders')
        opportunity_formset = OpportunityFormSet(request.POST, instance=startup, prefix='opportunities')
        funding_formset = FundingFormSet(request.POST, instance=startup, prefix='fundings')
        kpi_formset = KPIFormSet(request.POST, instance=startup, prefix='kpis')
        pitch_formset = PitchDeckFormSet(request.POST, request.FILES, instance=startup, prefix='pitches')
        service_formset = ServiceOfferedFormSet(request.POST, instance=startup, prefix='services')

        if (form.is_valid() and founder_formset.is_valid() and opportunity_formset.is_valid()
                and funding_formset.is_valid() and kpi_formset.is_valid()
                and pitch_formset.is_valid() and service_formset.is_valid()):
            saved_startup = form.save()
            founder_formset.save()
            opportunity_formset.save()
            funding_formset.save()
            kpi_formset.save()
            pitch_formset.save()
            service_formset.save()

            saved_startup.profile_completion = saved_startup.calc_profile_completion()
            saved_startup.save(update_fields=['profile_completion'])

            messages.success(request, 'Startup profile updated successfully.')
            return redirect('staff:startup_profile', slug=saved_startup.slug)
    else:
        form_class = StartupForm if profile and profile.is_admin else StartupOwnerForm
        form = form_class(instance=startup)
        founder_formset = FounderFormSet(instance=startup, prefix='founders')
        opportunity_formset = OpportunityFormSet(instance=startup, prefix='opportunities')
        funding_formset = FundingFormSet(instance=startup, prefix='fundings')
        kpi_formset = KPIFormSet(instance=startup, prefix='kpis')
        pitch_formset = PitchDeckFormSet(instance=startup, prefix='pitches')
        service_formset = ServiceOfferedFormSet(instance=startup, prefix='services')

    total_funding = sum(f.amount for f in startup.fundings.all())
    startup_achievements, startup_timeline = _startup_lifecycle_data(startup)
    profile_demo = _startup_profile_demo_data(startup)
    context = {
        'startup': startup,
        'form': form,
        'founder_formset': founder_formset,
        'opportunity_formset': opportunity_formset,
        'funding_formset': funding_formset,
        'kpi_formset': kpi_formset,
        'pitch_formset': pitch_formset,
        'service_formset': service_formset,
        'total_funding': total_funding,
        'startup_achievements': startup_achievements,
        **profile_demo,
        'startup_timeline': startup_timeline,
        'startup_industry_icon': _startup_industry_icon(startup.industry),
        'creating': False,
        'can_edit': can_edit,
        'can_view_private': can_view_private,
        'show_admin_fields': bool(profile and profile.is_admin),
        'more_login_url': more_login_url,
        'upcoming_mentor_sessions': startup.mentor_engagements.filter(
            status__in=('scheduled', 'confirmed'), date__gte=timezone.localdate()
        ).select_related('mentor').order_by('date', 'start_time')[:10] if can_view_mentor_sessions else (),
    }
    return render(request, 'startup_profile.html', context)


def partnership_form(request):
    """Handle partnership collaboration requests"""
    if request.method == 'POST':
        form = PartnershipForm(request.POST)
        if form.is_valid():
            partnership = form.save()
            PartnershipHistory.objects.create(
                partnership=partnership,
                old_status='',
                new_status=partnership.status,
                note='Partnership request submitted.',
            )
            messages.success(request, 'Partnership request submitted. We will be in touch.')
            return redirect('staff:partnership_success')
    else:
        form = PartnershipForm()
    return render(request, 'partnership_form.html', {'form': form})


def partnership_success(request):
    """Show partnership request success page"""
    return render(request, 'partnership_success.html')


def mentors(request):
    record_page_visit(request, 'mentor', 'directory', 'Mentor directory')
    queryset = Mentor.objects.filter(is_active=True)
    total_count = queryset.count()
    search_query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query) | Q(email__icontains=search_query)
            | Q(role__icontains=search_query) | Q(education_level__icontains=search_query)
            | Q(skills__icontains=search_query) | Q(training_topics__icontains=search_query)
        )
    if role_filter:
        queryset = queryset.filter(role__iexact=role_filter)
    page_params = request.GET.copy()
    page_params.pop('page', None)
    page_obj = Paginator(queryset.order_by('name'), 12).get_page(request.GET.get('page'))
    return render(request, 'mentors.html', {
        'mentors': page_obj,
        'page_obj': page_obj,
        'mentor_count': total_count,
        'roles': Mentor.objects.filter(is_active=True).exclude(role='').values_list('role', flat=True).distinct().order_by('role'),
        'search_query': search_query,
        'role_filter': role_filter,
        'page_query': page_params.urlencode(),
    })


def investors(request):
    record_page_visit(request, 'investor', 'directory', 'Investor directory')
    queryset = Investor.objects.filter(status='active')
    total_count = queryset.count()
    search_query = request.GET.get('q', '').strip()
    interest_filter = request.GET.get('interest', '').strip()
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query) | Q(organization__icontains=search_query)
            | Q(email__icontains=search_query) | Q(investment_interest__icontains=search_query)
            | Q(description__icontains=search_query)
        )
    if interest_filter:
        queryset = queryset.filter(investment_interest__iexact=interest_filter)
    page_params = request.GET.copy()
    page_params.pop('page', None)
    page_obj = Paginator(queryset.order_by('name', 'organization'), 12).get_page(request.GET.get('page'))
    return render(request, 'investors.html', {
        'investors': page_obj,
        'page_obj': page_obj,
        'investor_count': total_count,
        'interests': Investor.objects.filter(status='active').exclude(investment_interest='').values_list('investment_interest', flat=True).distinct().order_by('investment_interest'),
        'search_query': search_query,
        'interest_filter': interest_filter,
        'page_query': page_params.urlencode(),
    })


@login_required
def staff_list(request):
    profile = get_profile(request.user)
    if not profile.is_admin:
        messages.info(request, 'Staff account details are visible to administrators only.')
        return redirect('staff:dashboard')
    staff_users = User.objects.filter(is_staff=True, is_superuser=False, profile__user_type='staff').select_related('profile').order_by('first_name', 'username')
    return render(request, 'staff_list.html', {'staff_users': staff_users})


@login_required
def staff_home(request):
    """Landing page shown to staff (and admin) after signing in."""
    profile = get_profile(request.user)
    if not (request.user.is_superuser or profile.user_type in ('admin', 'staff')):
        return redirect('staff:dashboard')

    startups_qs = Startup.objects.all()
    pending = startups_qs.filter(status='pending').select_related().order_by('-created_at')
    context = {
        'counts': {
            'pending_startups': pending.count(),
            'active_startups': startups_qs.filter(status='active', directory_visible=True).count(),
            'mentors': Mentor.objects.filter(is_active=True).count(),
            'investors': Investor.objects.filter(status='active').count(),
            'staff': User.objects.filter(is_staff=True, is_superuser=False).count(),
        },
        'pending_startups': pending[:5],
    }
    return render(request, 'staff_home.html', context)


@login_required
@require_http_methods(['GET'])
def staff_management(request):
    """Admin workspace: manage staff accounts and monitor staff activity."""
    _require_account_admin(request)

    query = (request.GET.get('q') or '').strip()
    staff_qs = (
        User.objects.filter(Q(is_staff=True) | Q(profile__user_type='admin'))
        .select_related('profile').order_by('first_name', 'username')
    )
    if query:
        staff_qs = staff_qs.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query)
            | Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    staff_users = list(staff_qs)
    user_ids = [u.pk for u in staff_users]

    last_signin = {}
    login_totals = {}
    if user_ids:
        for note in LoginNotification.objects.filter(user_id__in=user_ids).order_by('-timestamp'):
            last_signin.setdefault(note.user_id, note)
        login_totals = {
            row['user_id']: row['n']
            for row in LoginNotification.objects.filter(user_id__in=user_ids)
            .values('user_id').annotate(n=Count('id'))
        }

    rows = []
    for user in staff_users:
        profile = get_profile(user)
        rows.append({
            'user': user,
            'role': 'Admin' if (user.is_superuser or profile.is_admin) else 'Staff',
            'is_admin_role': user.is_superuser or profile.is_admin,
            'last_signin': last_signin.get(user.pk),
            'login_total': login_totals.get(user.pk, 0),
        })

    today = timezone.localdate()
    all_scope = User.objects.filter(Q(is_staff=True) | Q(profile__user_type='admin'))
    activity = []
    for note in LoginNotification.objects.filter(user__in=all_scope).select_related('user')[:20]:
        activity.append({
            'when': note.timestamp, 'user': note.user,
            'event': 'Signed in', 'detail': f'IP {note.ip_address}', 'icon': 'fa-right-to-bracket',
        })
    for visit in PageVisit.objects.filter(visitor__in=all_scope).select_related('visitor')[:20]:
        activity.append({
            'when': visit.visited_at, 'user': visit.visitor,
            'event': f'Viewed {visit.get_page_type_display().lower()}',
            'detail': visit.display_name, 'icon': 'fa-eye',
        })
    activity.sort(key=lambda item: item['when'], reverse=True)
    activity = activity[:30]

    context = {
        'staff_rows': rows,
        'query': query,
        'stats': {
            'total': len(rows),
            'active': sum(1 for r in rows if r['user'].is_active),
            'disabled': sum(1 for r in rows if not r['user'].is_active),
            'admins': sum(1 for r in rows if r['is_admin_role']),
            'signins_today': LoginNotification.objects.filter(
                user__in=all_scope, timestamp__date=today,
            ).count(),
        },
        'activity': activity,
    }
    return render(request, 'staff_management.html', context)


@login_required
@require_http_methods(['POST'])
def staff_toggle(request, pk):
    """Enable or disable a staff login."""
    _require_account_admin(request)
    target = get_object_or_404(User, pk=pk, is_staff=True, is_superuser=False)
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    state = 'enabled' if target.is_active else 'disabled'
    messages.success(request, f'{target.get_full_name() or target.username} {state}.')
    return redirect('staff:staff_management')


def _require_account_admin(request, allow_staff=False):
    """Admin-only by default; pass allow_staff=True for startup management scope."""
    profile = get_profile(request.user)
    if request.user.is_superuser or profile.is_admin:
        return
    if allow_staff and profile.user_type == 'staff':
        return
    raise PermissionDenied


def _first_and_last(full_name):
    parts = (full_name or '').strip().split()
    return (parts[0], ' '.join(parts[1:])) if parts else ('Member', '')


def _unique_username(preferred):
    base = slugify(preferred) or 'member'
    candidate, suffix = base, 2
    while User.objects.filter(username=candidate).exists():
        candidate = f'{base}{suffix}'
        suffix += 1
    return candidate


def _provision_record_account(record, role):
    """Create a first-name login for an admin-managed person or startup record."""
    if role == 'startup':
        if UserProfile.objects.filter(startup=record).exists():
            return None
        full_name = record.name
        email = record.contact_email
        user_type = record.startup_type
    else:
        if record.user_id:
            return record.user.username
        full_name = record.name
        email = record.email
        user_type = role
    first_name, last_name = _first_and_last(full_name)
    username = _unique_username(first_name)
    user = User.objects.create_user(
        username=username, email=email or '', password='123',
        first_name=first_name, last_name=last_name,
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.user_type = user_type
    if role == 'startup':
        profile.startup = record
        profile.company_name = record.name
        profile.save(update_fields=['user_type', 'startup', 'company_name'])
    else:
        profile.save(update_fields=['user_type'])
        record.user = user
        record.save(update_fields=['user'])
    return username


@login_required
@require_http_methods(['GET', 'POST'])
def account_management(request):
    _require_account_admin(request, allow_staff=True)
    if request.method == 'POST' and request.POST.get('action') == 'provision_existing':
        _require_account_admin(request)  # provisioning mentors/investors stays admin-only
        created = []
        for kind, queryset in (
            ('startup', Startup.objects.all()),
            ('mentor', Mentor.objects.filter(is_active=True)),
            ('investor', Investor.objects.filter(status='active')),
        ):
            for record in queryset.iterator():
                username = _provision_record_account(record, kind)
                if username:
                    created.append(f'{record}: {username}')
        messages.success(request, f'Created {len(created)} login account(s) using the shared initial password 123.')
        return redirect('staff:account_management')

    return render(request, 'account_management.html', {
        'startups': Startup.objects.select_related().all()[:100],
        'mentors': Mentor.objects.filter(is_active=True).select_related('user')[:100],
        'investors': Investor.objects.filter(status='active').select_related('user')[:100],
        'staff_users': User.objects.filter(is_staff=True, is_superuser=False, profile__user_type='staff').select_related('profile').order_by('first_name', 'username'),
        'pending_startups': Startup.objects.filter(status='pending').count(),
        'counts': {
            'startups': Startup.objects.count(), 'mentors': Mentor.objects.filter(is_active=True).count(),
            'investors': Investor.objects.filter(status='active').count(),
            'staff': User.objects.filter(is_staff=True, is_superuser=False, profile__user_type='staff').count(),
        },
    })


@login_required
@require_http_methods(['GET', 'POST'])
def account_add(request, kind):
    _require_account_admin(request, allow_staff=(kind == 'startup'))
    forms_by_kind = {'startup': StartupForm, 'mentor': MentorForm, 'investor': InvestorForm, 'staff': ManagedUserForm}
    if kind not in forms_by_kind:
        raise PermissionDenied
    form = forms_by_kind[kind](request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        if kind == 'staff':
            user = form.save(commit=False)
            user.first_name = user.first_name.strip()
            user.username = _unique_username(user.first_name or user.username)
            user.is_staff = True
            user.is_superuser = False
            user.set_password('123')
            user.save()
            profile = get_profile(user)
            profile.user_type = 'staff'
            profile.save(update_fields=['user_type'])
            messages.success(request, f'Staff account created. Username: {user.username}; initial password: 123.')
        else:
            record = form.save(commit=False)
            if kind == 'startup':
                record.startup_type = 'public'
                record.status = 'active'
                record.directory_visible = True
            record.save()
            username = _provision_record_account(record, kind)
            messages.success(request, f'{record} created. Username: {username}; initial password: 123.')
        return redirect('staff:account_management')
    return render(request, 'account_form.html', {'form': form, 'kind': kind, 'heading': f'Add {kind.title()}', 'is_new': True})


@login_required
@require_http_methods(['GET', 'POST'])
def account_edit(request, kind, pk):
    _require_account_admin(request, allow_staff=(kind == 'startup'))
    models_by_kind = {'startup': (Startup, StartupForm), 'mentor': (Mentor, MentorForm), 'investor': (Investor, InvestorForm), 'staff': (User, ManagedUserForm)}
    if kind not in models_by_kind:
        raise PermissionDenied
    model, form_class = models_by_kind[kind]
    queryset = User.objects.filter(is_staff=True, is_superuser=False) if kind == 'staff' else model.objects.all()
    record = get_object_or_404(queryset, pk=pk)
    form = form_class(request.POST or None, request.FILES or None, instance=record)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        if kind == 'startup':
            for profile in saved.users.select_related('user'):
                profile.user_type = saved.startup_type
                profile.company_name = saved.name
                profile.save(update_fields=['user_type', 'company_name'])
        elif kind in ('mentor', 'investor') and saved.user_id:
            first_name, last_name = _first_and_last(saved.name)
            saved.user.first_name, saved.user.last_name, saved.user.email = first_name, last_name, saved.email
            saved.user.is_active = saved.is_active if kind == 'mentor' else saved.status == 'active'
            saved.user.save(update_fields=['first_name', 'last_name', 'email', 'is_active'])
        messages.success(request, f'{saved} updated.')
        return redirect('staff:account_management')
    return render(request, 'account_form.html', {'form': form, 'kind': kind, 'heading': f'Edit {kind.title()}', 'is_new': False})


@login_required
@require_http_methods(['POST'])
def account_delete(request, kind, pk):
    _require_account_admin(request, allow_staff=(kind == 'startup'))
    if kind == 'staff':
        record = get_object_or_404(User, pk=pk, is_staff=True, is_superuser=False)
    elif kind == 'startup':
        record = get_object_or_404(Startup, pk=pk)
    elif kind == 'mentor':
        record = get_object_or_404(Mentor, pk=pk)
    elif kind == 'investor':
        record = get_object_or_404(Investor, pk=pk)
    else:
        raise PermissionDenied
    label = str(record)
    if kind != 'staff':
        linked_user = getattr(record, 'user', None) if kind in ('mentor', 'investor') else UserProfile.objects.filter(startup=record).select_related('user').first()
        if kind == 'startup' and linked_user:
            linked_user = linked_user.user
        if linked_user:
            linked_user.delete()
    record.delete()
    messages.success(request, f'{label} deleted.')
    return redirect('staff:account_management')


@login_required
@require_http_methods(['POST'])
def startup_decision(request, pk, decision):
    _require_account_admin(request, allow_staff=True)
    startup = get_object_or_404(Startup, pk=pk)
    if decision not in ('approve', 'reject'):
        raise PermissionDenied
    startup.status = 'active' if decision == 'approve' else 'inactive'
    startup.directory_visible = decision == 'approve'
    startup.save(update_fields=['status', 'directory_visible', 'updated_at'])
    messages.success(request, f'{startup.name} {"approved and published" if decision == "approve" else "rejected"}.')
    return redirect('staff:account_management')
