from .models import Investor, Mentor, PageVisit, Startup, UserProfile


def people_counts(request):
    return {
        'live_counts': {
            'startups': Startup.objects.count(),
            'mentors': Mentor.objects.filter(is_active=True).count(),
            'investors': Investor.objects.filter(status='active').count(),
        }
    }


def admin_page_visit_alerts(request):
    unread = 0
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        if user.is_superuser or UserProfile.objects.filter(user=user, user_type='admin').exists():
            unread = PageVisit.objects.filter(is_read=False).count()
    return {'unread_page_visit_count': unread}
