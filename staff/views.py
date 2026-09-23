from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from .models import (
    Startup, Founder, Opportunity, Funding,
    KPI, PitchDeck, ServiceOffered, Partnership,
    UserProfile, RegistrationRate, ProfileView, LoginNotification
)
from .forms import (
    StartupForm, StartupOwnerForm, FounderFormSet, OpportunityFormSet,
    FundingFormSet, KPIFormSet, PitchDeckFormSet,
    ServiceOfferedFormSet, PartnershipForm
)

User = get_user_model()


def get_profile(user):
    """Return the user's profile, creating it when it does not exist yet."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def landing(request):
    """Public landing page for visitors, dashboard for logged-in users."""
    if request.user.is_authenticated:
        return index(request)
    return render(request, 'landing.html')


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
    startup_list = Startup.objects.all()
    # Filter by type if specified
    startup_type = request.GET.get('type')
    if startup_type:
        startup_list = startup_list.filter(startup_type=startup_type)
    context = {'startup_list': startup_list, 'filter_type': startup_type}
    return render(request, 'startups.html', context)


@require_http_methods(["GET", "POST"])
def user_login(request):
    """Handle user login with type-based authentication"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'public')  # admin, public, individual

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Get or create user profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            if created and (user.is_staff or user.is_superuser):
                profile.user_type = 'admin'
                profile.save(update_fields=['user_type'])
            # Update login count
            profile.login_count += 1
            profile.last_login_ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            profile.save()

            # Determine user type for redirect
            if profile.is_admin:
                return redirect('staff:dashboard')
            elif profile.is_startup:
                # Redirect to startup profile or create
                if profile.startup:
                    return redirect('staff:startup_profile', slug=profile.startup.slug)
                else:
                    # Redirect to startup creation
                    return redirect('staff:startup_create')
            else:
                return redirect('staff:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    user_types = UserProfile.USER_TYPE_CHOICES
    return render(request, 'registration/login.html', {'user_types': user_types})


@require_http_methods(["GET", "POST"])
def user_logout(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('staff:dashboard')


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
    """Handle user registration with type selection"""
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'public')  # public, individual

        # Self-registered accounts can never claim admin rights.
        if user_type not in ('public', 'individual'):
            user_type = 'public'

        if not username or not password:
            messages.error(request, 'Username and password are required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            # Create user profile with selected type
            UserProfile.objects.create(
                user=user,
                user_type=user_type,
            )

            # Log the user in
            login(request, user)

            # A startup account lands directly on the startup creation form
            messages.success(request, 'Welcome! Add your startup to get started.')
            return redirect('staff:startup_create')

    user_types = [c for c in UserProfile.USER_TYPE_CHOICES if c[0] != 'admin']
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
                startup = form.save()
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


@login_required
def startup_profile(request, slug):
    """Display and edit startup profile"""
    startup = get_object_or_404(Startup, slug=slug)
    profile = get_profile(request.user)

    # Only the owner of the startup (or a hub admin) may change it.
    can_edit = profile.is_admin or request.user.is_staff or profile.startup_id == startup.id

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
        form_class = StartupForm if profile.is_admin else StartupOwnerForm
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
        'show_admin_fields': profile.is_admin,
    }
    return render(request, 'startup_profile.html', context)


def partnership_form(request):
    """Handle partnership collaboration requests"""
    if request.method == 'POST':
        form = PartnershipForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Partnership request submitted. We will be in touch.')
            return redirect('staff:partnership_success')
    else:
        form = PartnershipForm()
    return render(request, 'partnership_form.html', {'form': form})


def partnership_success(request):
    """Show partnership request success page"""
    return render(request, 'partnership_success.html')


def mentors(request):
    return render(request, 'mentors.html')


def investors(request):
    return render(request, 'investors.html')


def staff_list(request):
    return render(request, 'staff_list.html')