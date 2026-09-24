from .models import Investor, Mentor, Startup


def people_counts(request):
    return {
        'live_counts': {
            'startups': Startup.objects.count(),
            'mentors': Mentor.objects.filter(is_active=True).count(),
            'investors': Investor.objects.filter(status='active').count(),
        }
    }