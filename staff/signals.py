from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.contrib.contenttypes.models import ContentType
from .models import UserProfile, ProfileView, LoginNotification, RegistrationRate


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Send notification to admins when any user logs in"""
    # Create login notification
    LoginNotification.objects.create(
        user=user,
        ip_address=getattr(request, 'META', {}).get('REMOTE_ADDR', '0.0.0.0'),
    )

    # If admin user, could send additional notification
    # This would be handled in the template/dashboard


@receiver(post_save)
def track_profile_view(sender, instance, created, **kwargs):
    """Track profile views for notification purposes"""
    # If a UserProfile is created/saved, ensure it has proper defaults
    if isinstance(instance, UserProfile):
        if not instance.startup and instance.user_type in ['public', 'individual']:
            # Ensure startup is linked if needed
            pass


@receiver(post_migrate)
def create_default_rates(sender, **kwargs):
    """Create default registration rate entries"""
    # Create all_date entry
    if not RegistrationRate.objects.filter(date_range='all_time').exists():
        RegistrationRate.objects.create(date_range='all_time')

    # Create today entry
    if not RegistrationRate.objects.filter(date_range='today').exists():
        RegistrationRate.objects.create(date_range='today')

    # Create this_month entry
    if not RegistrationRate.objects.filter(date_range='this_month').exists():
        RegistrationRate.objects.create(date_range='this_month')


@receiver(post_migrate)
def create_default_rates(sender, **kwargs):
    """Create default registration rate entries"""
    from .models import RegistrationRate

    # Create all_date entry
    if not RegistrationRate.objects.filter(date_range='all_time').exists():
        RegistrationRate.objects.create(date_range='all_time')

    # Create today entry
    if not RegistrationRate.objects.filter(date_range='today').exists():
        RegistrationRate.objects.create(date_range='today')

    # Create this_month entry
    if not RegistrationRate.objects.filter(date_range='this_month').exists():
        RegistrationRate.objects.create(date_range='this_month')