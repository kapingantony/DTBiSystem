from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.contrib.auth.models import User


class Startup(models.Model):
    TYPE_CHOICES = [
        ('public', 'Public'),
        ('individual', 'Individual'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
    ]

    CONTRACT_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    startup_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='public')
    description = models.TextField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='startups/logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='startups/covers/', blank=True, null=True)

    # Incubation
    founded_date = models.DateField(null=True, blank=True)
    incubation_start = models.DateField(null=True, blank=True)
    incubation_end = models.DateField(null=True, blank=True)
    year_incubated = models.PositiveIntegerField(null=True, blank=True)

    # Contract
    contract_status = models.CharField(max_length=20, choices=CONTRACT_CHOICES, default='draft', blank=True)

    # Profile
    profile_completion = models.PositiveIntegerField(default=0, help_text='Percentage of profile completed')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'startup'
            slug = base
            suffix = 1
            qs = Startup.objects.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                suffix += 1
                slug = f'{base}-{suffix}'
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('staff:startup_profile', kwargs={'slug': self.slug})

    def calc_profile_completion(self):
        fields = [
            self.description, self.industry, self.website,
            self.founded_date, self.incubation_start,
        ]
        filled = sum(1 for f in fields if f)
        has_founder = self.founders.exists()
        has_opportunity = self.opportunities.exists()
        has_kpi = self.kpis.exists()
        has_pitch = self.pitch_decks.exists()
        has_service = self.services.exists()

        total = len(fields) + 4
        filled += sum([has_founder, has_opportunity, has_kpi, has_pitch, has_service])
        return round((filled / total) * 100) if total else 0


class Founder(models.Model):
    ROLE_CHOICES = [
        ('founder', 'Founder'),
        ('co_founder', 'Co-Founder'),
    ]

    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='founders')
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='founder')
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='founders/avatars/', blank=True, null=True)
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


class Opportunity(models.Model):
    TYPE_CHOICES = [
        ('funding', 'Funding'),
        ('mentorship', 'Mentorship'),
        ('partnership', 'Partnership'),
        ('market_access', 'Market Access'),
        ('acceleration', 'Acceleration'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('filled', 'Filled'),
    ]

    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='opportunities')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    opportunity_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='funding')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Funding(models.Model):
    TYPE_CHOICES = [
        ('pre_seed', 'Pre-Seed'),
        ('seed', 'Seed'),
        ('series_a', 'Series A'),
        ('series_b', 'Series B'),
        ('series_c', 'Series C'),
        ('grant', 'Grant'),
        ('debt', 'Debt'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('committed', 'Committed'),
        ('received', 'Received'),
        ('pending', 'Pending'),
        ('declined', 'Declined'),
    ]

    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='fundings')
    source = models.CharField(max_length=255, help_text='Investor or fund name')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    funding_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='seed')
    date_received = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='committed')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} — ${self.amount:,.0f}"

    @property
    def formatted_amount(self):
        if self.amount >= 1_000_000:
            return f"${self.amount / 1_000_000:.1f}M"
        elif self.amount >= 1_000:
            return f"${self.amount / 1_000:.0f}K"
        return f"${self.amount:,.0f}"


class KPI(models.Model):
    PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]

    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='kpis')
    metric_name = models.CharField(max_length=255)
    metric_value = models.DecimalField(max_digits=12, decimal_places=2)
    target_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='monthly')
    unit = models.CharField(max_length=50, blank=True, help_text='e.g. users, revenue, %')
    date_recorded = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.metric_name}: {self.metric_value} {self.unit}"

    @property
    def achievement_pct(self):
        if self.target_value and self.target_value > 0:
            return round((self.metric_value / self.target_value) * 100)
        return None


class PitchDeck(models.Model):
    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='pitch_decks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='pitch_decks/', blank=True, null=True)
    presentation_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ServiceOffered(models.Model):
    CATEGORY_CHOICES = [
        ('technology', 'Technology'),
        ('consulting', 'Consulting'),
        ('financial', 'Financial Services'),
        ('marketing', 'Marketing'),
        ('logistics', 'Logistics'),
        ('education', 'Education'),
        ('healthcare', 'Healthcare'),
        ('agriculture', 'Agriculture'),
        ('other', 'Other'),
    ]

    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('individual', 'Individual Startup'),
        ('public', 'Public Startup'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='public')
    startup = models.ForeignKey(
        'Startup', on_delete=models.CASCADE, null=True, blank=True, related_name='users'
    )
    company_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='users/avatars/', blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    company_website = models.URLField(blank=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    is_email_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True)
    date_verified = models.DateTimeField(null=True, blank=True)
    theme = models.CharField(
        max_length=20,
        choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'Use device setting')],
        default='light',
    )
    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_user_type_display})"

    @property
    def is_admin(self):
        return self.user_type == 'admin'

    @property
    def is_staff_role(self):
        return self.user_type in ['admin', 'staff']

    @property
    def is_startup(self):
        return self.user_type in ['public', 'individual']

    @property
    def startup_name(self):
        return self.startup.name if self.startup else self.company_name


class RegistrationRate(models.Model):
    """Tracks registration rates and statistics"""
    DATE_CHOICES = [
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('all_time', 'All Time'),
    ]

    date_range = models.CharField(max_length=20, choices=DATE_CHOICES, default='all_time')
    total_registrations = models.PositiveIntegerField(default=0)
    new_today = models.PositiveIntegerField(default=0)
    active_users_today = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Registration Rate"
        verbose_name_plural = "Registration Rates"

    def __str__(self):
        return f"{self.get_date_range_display}: {self.total_registrations} registrations"


class ProfileView(models.Model):
    """Tracks profile views for notification purposes"""
    viewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='viewed_profiles'
    )
    viewed_profile_owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='profile_views_received'
    )
    startup = models.ForeignKey(
        'Startup', on_delete=models.CASCADE, null=True, blank=True
    )
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Profile View"
        verbose_name_plural = "Profile Views"
        ordering = ['-viewed_at']
        unique_together = ['viewer', 'viewed_profile_owner', 'startup']

    def __str__(self):
        return f"{self.viewer.username} viewed {self.viewed_profile_owner.username}'s profile"


class LoginNotification(models.Model):
    """Tracks login notifications for admins"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='login_notifications'
    )
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    startup_type = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        verbose_name = "Login Notification"
        verbose_name_plural = "Login Notifications"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} logged in at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class SiteVisit(models.Model):
    """Stores one current visitor record per browser session."""
    session_key = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='site_visits'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f"Visitor {self.session_key}"


class Partnership(models.Model):
    TYPE_CHOICES = [
        ('strategic', 'Strategic Partnership'),
        ('technical', 'Technical Collaboration'),
        ('distribution', 'Distribution Partnership'),
        ('research', 'Research Collaboration'),
        ('investment', 'Investment Partnership'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('under_review', 'Under Review'),
    ]

    startup_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    partnership_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='strategic')
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.startup_name} — {self.contact_name}"