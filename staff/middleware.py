from .models import SiteVisit


class SiteVisitMiddleware:
    """Record one visitor per browser session for application page requests."""

    excluded_prefixes = ('/static/', '/media/', '/favicon.ico')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.excluded_prefixes):
            if not request.session.session_key:
                request.session.create()
            SiteVisit.objects.update_or_create(
                session_key=request.session.session_key,
                defaults={
                    'user': request.user if request.user.is_authenticated else None,
                    'ip_address': request.META.get('REMOTE_ADDR'),
                },
            )
        return self.get_response(request)
