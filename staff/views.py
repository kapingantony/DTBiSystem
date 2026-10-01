from io import BytesIO

from openpyxl import Workbook

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.http import urlencode, url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.http import Http404, HttpResponse, JsonResponse

from .models import (
    Startup, Founder, Opportunity, Funding,
    KPI, PitchDeck, ServiceOffered, Partnership, PartnershipHistory,
    UserProfile, RegistrationRate, ProfileView, LoginNotification, SiteVisit,
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
    """Year based public impact view using recorded operational data only."""
    from .models import ParticipantJourney, ParticipantOutcome, MentorEngagement

    current_year = timezone.localdate().year
    years = range(2000, current_year + 1)
    try:
        selected_year = int(request.GET.get('year', current_year))
    except (TypeError, ValueError):
        selected_year = current_year
    if selected_year not in years:
        selected_year = current_year
    selected_startup = request.GET.get('startup', '').strip()
    visible_startups = Startup.objects.filter(directory_visible=True).exclude(status='pending')
    startup_query = visible_startups
    if selected_startup.isdigit():
        startup_query = startup_query.filter(pk=selected_startup)
    else:
        selected_startup = ''
    startup = startup_query.first() if selected_startup else None

    cohort = visible_startups.filter(
        Q(year_incubated=selected_year)
        | Q(year_incubated__isnull=True, incubation_start__year=selected_year)
        | Q(year_incubated__isnull=True, incubation_start__isnull=True, founded_date__year=selected_year)
    )
    journeys = ParticipantJourney.objects.filter(started_on__year=selected_year, startup__in=visible_startups)
    outcomes = ParticipantOutcome.objects.filter(recorded_on__year=selected_year, journey__startup__in=visible_startups)
    if startup:
        cohort = cohort.filter(pk=startup.pk)
        journeys = journeys.filter(startup=startup)
        outcomes = outcomes.filter(journey__startup=startup)
    latest_outcomes = [
        row for row in outcomes.select_related('journey__startup').order_by('journey_id', '-recorded_on', '-created_at')
    ]
    latest_by_journey = {}
    for outcome in latest_outcomes:
        latest_by_journey.setdefault(outcome.journey_id, outcome)
    outcome_rows = list(latest_by_journey.values())
    jobs_full = sum(row.full_time_jobs for row in outcome_rows)
    jobs_part = sum(row.part_time_jobs for row in outcome_rows)
    sessions = MentorEngagement.objects.filter(date__year=selected_year, status='completed', startup__in=visible_startups)
    if startup:
        sessions = sessions.filter(startup=startup)
    cohort_ids = set(cohort.values_list('pk', flat=True))
    journey_ids = set(journeys.values_list('startup_id', flat=True))
    outcome_ids = set(ParticipantOutcome.objects.filter(recorded_on__year=selected_year, journey__startup__in=visible_startups).values_list('journey__startup_id', flat=True))
    session_ids = set(sessions.values_list('startup_id', flat=True))
    dataset = request.GET.get('dataset', 'all')
    dataset_choices = [('all', 'All annual data'), ('startups', 'Startup cohorts'), ('participants', 'Participant outcomes'), ('mentoring', 'Mentoring activity')]
    if dataset not in {key for key, _label in dataset_choices}:
        dataset = 'all'
    candidate_ids = {
        'all': cohort_ids | journey_ids | outcome_ids | session_ids,
        'startups': cohort_ids,
        'participants': journey_ids | outcome_ids,
        'mentoring': session_ids,
    }[dataset]
    if startup:
        candidate_ids = {startup.pk}
    startup_rows = []
    for item in visible_startups.filter(pk__in=candidate_ids).order_by('name'):
        item_journeys = ParticipantJourney.objects.filter(startup=item, started_on__year=selected_year)
        item_outcomes = ParticipantOutcome.objects.filter(journey__startup=item, recorded_on__year=selected_year)
        latest_for_journey = {}
        for item_outcome in item_outcomes.order_by('journey_id', '-recorded_on', '-created_at'):
            latest_for_journey.setdefault(item_outcome.journey_id, item_outcome)
        item_sessions = MentorEngagement.objects.filter(startup=item, date__year=selected_year, status='completed').count()
        startup_rows.append({
            'startup': item, 'in_cohort': item.pk in cohort_ids,
            'participant_starts': item_journeys.count(), 'outcome_snapshots': item_outcomes.count(),
            'milestones': item_outcomes.exclude(milestone='').count(), 'mentor_sessions': item_sessions,
            'full_time_jobs': sum(outcome.full_time_jobs for outcome in latest_for_journey.values()),
            'part_time_jobs': sum(outcome.part_time_jobs for outcome in latest_for_journey.values()),
        })

    max_jobs = max((row['full_time_jobs'] + row['part_time_jobs'] for row in startup_rows), default=0)
    for row in startup_rows:
        row['jobs_total'] = row['full_time_jobs'] + row['part_time_jobs']
        row['jobs_bar_width'] = round((row['jobs_total'] / max_jobs) * 100) if max_jobs else 0

    if request.GET.get('format') == 'xlsx':
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Annual startup impact'
        sheet.append(['Startup', 'Industry', 'Year', 'In startup cohort', 'Participant starts', 'Completed mentoring sessions', 'Outcome snapshots', 'Milestone updates', 'Reported full-time jobs', 'Reported part-time jobs'])
        for row in startup_rows:
            sheet.append([row['startup'].name, row['startup'].industry, selected_year, 'Yes' if row['in_cohort'] else 'No', row['participant_starts'], row['mentor_sessions'], row['outcome_snapshots'], row['milestones'], row['full_time_jobs'], row['part_time_jobs']])
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(max(max(len(str(cell.value or '')) for cell in column) + 2, 12), 36)
        output = BytesIO()
        workbook.save(output)
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="dtbi-impact-{selected_year}-{dataset}.xlsx"'
        return response
    return render(request, 'impact_explorer.html', {
        'years': years, 'selected_year': selected_year, 'startups': visible_startups.order_by('name'),
        'selected_startup': str(startup.pk) if startup else '', 'startup': startup,
        'startup_count': cohort.distinct().count(), 'participant_count': journeys.count(),
        'jobs_full': jobs_full, 'jobs_part': jobs_part, 'sessions_count': sessions.count(),
        'outcome_count': outcomes.count(),
        'startup_rows': startup_rows, 'dataset': dataset, 'dataset_choices': dataset_choices,
        'jobs_chart_max': max_jobs,
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
    startup_list = Startup.objects.filter(directory_visible=True).prefetch_related('founders')
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
    if industry_filter:
        startup_list = startup_list.filter(industry__iexact=industry_filter)
    if status_filter in dict(Startup.STATUS_CHOICES):
        startup_list = startup_list.filter(status=status_filter)
    industries = list(Startup.objects.filter(directory_visible=True).exclude(industry='').values_list('industry', flat=True).distinct().order_by('industry'))
    industry_options = [{'value': category, 'label': category} for category in industries]
    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_obj = Paginator(startup_list, 6).get_page(request.GET.get('page'))
    from django.utils import timezone
    current_year = timezone.localdate().year
    context = {
        'startup_list': page_obj,
        'impact_years': range(2000, current_year + 1),
        'impact_default_year': current_year,
        'impact_startups': Startup.objects.filter(directory_visible=True).exclude(status='pending').order_by('name'),
        'page_obj': page_obj,
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


def _require_account_admin(request):
    profile = get_profile(request.user)
    if not (request.user.is_superuser or profile.is_admin):
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
    _require_account_admin(request)
    if request.method == 'POST' and request.POST.get('action') == 'provision_existing':
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
    _require_account_admin(request)
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
    _require_account_admin(request)
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
    _require_account_admin(request)
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
    _require_account_admin(request)
    startup = get_object_or_404(Startup, pk=pk)
    if decision not in ('approve', 'reject'):
        raise PermissionDenied
    startup.status = 'active' if decision == 'approve' else 'inactive'
    startup.directory_visible = decision == 'approve'
    startup.save(update_fields=['status', 'directory_visible', 'updated_at'])
    messages.success(request, f'{startup.name} {"approved and published" if decision == "approve" else "rejected"}.')
    return redirect('staff:account_management')
