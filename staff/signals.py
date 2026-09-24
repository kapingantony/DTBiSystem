from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import LoginNotification, RegistrationRate, UserProfile

User = get_user_model()


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Send notification to admins when any user logs in."""
    LoginNotification.objects.create(
        user=user,
        ip_address=getattr(request, 'META', {}).get('REMOTE_ADDR', '0.0.0.0'),
    )


@receiver(post_save, sender=User)
def sync_user_profile_role(sender, instance, created, **kwargs):
    """Keep the custom app role aligned with Django auth flags."""
    profile, _ = UserProfile.objects.get_or_create(user=instance)

    if instance.is_superuser:
        profile.user_type = 'admin'
        if not instance.is_staff:
            instance.is_staff = True
            instance.save(update_fields=['is_staff'])
    elif instance.is_staff:
        profile.user_type = 'staff'
    elif profile.user_type in {'admin', 'staff'}:
        profile.user_type = 'public'
    elif not profile.user_type:
        profile.user_type = 'public'

    profile.save(update_fields=['user_type'])


@receiver(post_migrate)
def create_default_rates(sender, **kwargs):
    """Create default registration rate entries used by the dashboard."""
    if not RegistrationRate.objects.filter(date_range='all_time').exists():
        RegistrationRate.objects.create(date_range='all_time')
    if not RegistrationRate.objects.filter(date_range='today').exists():
        RegistrationRate.objects.create(date_range='today')
    if not RegistrationRate.objects.filter(date_range='this_month').exists():
        RegistrationRate.objects.create(date_range='this_month')