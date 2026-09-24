from django import forms
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone
from .models import (
    Startup, Founder, Opportunity, Funding,
    KPI, PitchDeck, ServiceOffered, Partnership, UserProfile, Mentor, Investor,
    MentorEngagement, ParticipantJourney, ParticipantSupport, ParticipantFollowUp,
    ParticipantOutcome,
)


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
        }


class ProfilePreferencesForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['company_name', 'bio', 'phone', 'company_website', 'theme', 'email_notifications']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-input'}),
            'bio': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'company_website': forms.URLInput(attrs={'class': 'form-input'}),
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'settings-checkbox'}),
        }


class StartupForm(forms.ModelForm):
    class Meta:
        model = Startup
        fields = [
            'name', 'startup_type', 'description', 'industry', 'website',
            'contact_email', 'phone', 'source',
            'logo', 'cover_image', 'founded_date', 'incubation_start',
            'incubation_end', 'year_incubated', 'contract_status', 'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Startup name'}),
            'startup_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Brief description of the startup...'}),
            'industry': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Fintech, AgriTech'}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'startup@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'source': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'BUNI workbook'}),
            'founded_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'incubation_start': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'incubation_end': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'year_incubated': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 2024'}),
            'contract_status': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class StartupOwnerForm(StartupForm):
    """Startup form limited to the fields an owner is allowed to set.

    Status remains admin-managed, but startup owners can update the basic
    contract and incubation details needed on their profile.
    """

    class Meta(StartupForm.Meta):
        fields = [
            'name', 'startup_type', 'description', 'industry', 'website',
            'contact_email', 'phone',
            'logo', 'cover_image', 'founded_date', 'year_incubated',
            'contract_status',
        ]


class FounderForm(forms.ModelForm):
    class Meta:
        model = Founder
        fields = ['name', 'email', 'phone', 'role', 'bio', 'avatar', 'linkedin', 'twitter']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Short bio...'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'LinkedIn URL'}),
            'twitter': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'Twitter URL'}),
        }


class MentorForm(forms.ModelForm):
    class Meta:
        model = Mentor
        fields = ['name', 'email', 'gender', 'education_level', 'phone', 'role', 'skills', 'training_topics', 'is_active']


class InvestorForm(forms.ModelForm):
    class Meta:
        model = Investor
        fields = ['name', 'organization', 'email', 'phone', 'website', 'description', 'investment_interest', 'status']


FounderFormSet = forms.inlineformset_factory(
    Startup, Founder, form=FounderForm,
    extra=1, can_delete=True, min_num=1, validate_min=True
)


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ['title', 'description', 'opportunity_type', 'status', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Opportunity title'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Describe this opportunity...'}),
            'opportunity_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'deadline': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


OpportunityFormSet = forms.inlineformset_factory(
    Startup, Opportunity, form=OpportunityForm,
    extra=1, can_delete=True
)


class FundingForm(forms.ModelForm):
    class Meta:
        model = Funding
        fields = ['investor', 'source', 'amount', 'currency', 'funding_type', 'date_received', 'status', 'notes']
        widgets = {
            'investor': forms.Select(attrs={'class': 'form-select'}),
            'source': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Investor or fund name'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00'}),
            'currency': forms.TextInput(attrs={'class': 'form-input', 'maxlength': 3, 'placeholder': 'USD'}),
            'funding_type': forms.Select(attrs={'class': 'form-select'}),
            'date_received': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Additional notes...'}),
        }


FundingFormSet = forms.inlineformset_factory(
    Startup, Funding, form=FundingForm,
    extra=1, can_delete=True
)


class KPIForm(forms.ModelForm):
    class Meta:
        model = KPI
        fields = ['metric_name', 'metric_value', 'target_value', 'period', 'unit']
        widgets = {
            'metric_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Monthly Active Users'}),
            'metric_value': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0'}),
            'target_value': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. users, revenue, %'}),
        }


KPIFormSet = forms.inlineformset_factory(
    Startup, KPI, form=KPIForm,
    extra=1, can_delete=True
)


class PitchDeckForm(forms.ModelForm):
    class Meta:
        model = PitchDeck
        fields = ['title', 'description', 'file', 'presentation_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Deck title'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'What this pitch covers...'}),
            'file': forms.FileInput(attrs={'class': 'form-input'}),
            'presentation_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


PitchDeckFormSet = forms.inlineformset_factory(
    Startup, PitchDeck, form=PitchDeckForm,
    extra=1, can_delete=True
)


class ServiceOfferedForm(forms.ModelForm):
    class Meta:
        model = ServiceOffered
        fields = ['name', 'description', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Service name'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Describe the service...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }


ServiceOfferedFormSet = forms.inlineformset_factory(
    Startup, ServiceOffered, form=ServiceOfferedForm,
    extra=1, can_delete=True
)


class PartnershipForm(forms.ModelForm):
    proposed_contribution = forms.CharField(
        label='What your organization can contribute',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Funding, expertise, mentorship, market access, facilities, technology, or another resource'}),
    )
    startup_benefit = forms.CharField(
        label='How this will benefit startups',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Describe the startups or programme needs this will support'}),
    )
    expected_outcomes = forms.CharField(
        label='Expected outcomes',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'What measurable result or change do you expect?'}),
    )

    class Meta:
        model = Partnership
        fields = [
            'startup_name', 'contact_name', 'email', 'phone',
            'organization', 'related_startup', 'partnership_type',
            'proposed_contribution', 'startup_benefit', 'expected_outcomes', 'message'
        ]
        widgets = {
            'startup_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your organization or startup name'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'organization': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Organization (if any)'}),
            'related_startup': forms.Select(attrs={'class': 'form-select'}),
            'partnership_type': forms.Select(attrs={'class': 'form-select'}),
            'message': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Share background, intended activities, timing, or other details...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['related_startup'].required = False
        self.fields['related_startup'].queryset = Startup.objects.filter(status='active').order_by('name')


class MentorEngagementScheduleForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=(('scheduled', 'Scheduled'), ('confirmed', 'Confirmed')),
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='scheduled',
    )

    class Meta:
        model = MentorEngagement
        fields = [
            'mentor', 'startup', 'date', 'start_time', 'hours', 'topics',
            'meeting_location', 'meeting_url', 'status',
        ]
        widgets = {
            'mentor': forms.Select(attrs={'class': 'form-select'}),
            'startup': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'hours': forms.NumberInput(attrs={'class': 'form-input', 'min': '0.25', 'max': '8', 'step': '0.25'}),
            'topics': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Topics or intended session outcomes'}),
            'meeting_location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Office, venue, or online platform'}),
            'meeting_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://... (optional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mentor'].queryset = Mentor.objects.filter(is_active=True).order_by('name')
        self.fields['startup'].queryset = Startup.objects.filter(status='active').order_by('name')
        self.fields['hours'].initial = 1
        self.fields['meeting_location'].label = 'Meeting place or instructions'

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('date')
        start_time = cleaned.get('start_time')
        hours = cleaned.get('hours')
        mentor = cleaned.get('mentor')
        startup = cleaned.get('startup')
        if not cleaned.get('meeting_location') and not cleaned.get('meeting_url'):
            self.add_error('meeting_location', 'Add a meeting place/instruction or an online meeting link.')
        if not all((date, start_time, hours, mentor, startup)):
            return cleaned

        start = datetime.combine(date, start_time)
        end = start + timedelta(hours=float(hours))
        conflicts = MentorEngagement.objects.filter(
            date=date, status__in=('scheduled', 'confirmed'), start_time__isnull=False,
        ).filter(Q(mentor=mentor) | Q(startup=startup))
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)
        for session in conflicts.select_related('mentor', 'startup'):
            existing_start = datetime.combine(session.date, session.start_time)
            existing_end = existing_start + timedelta(hours=float(session.hours))
            if start < existing_end and existing_start < end:
                if session.mentor_id == mentor.pk:
                    self.add_error('mentor', f'{mentor.name} already has a session from {session.start_time:%H:%M} for this period.')
                if session.startup_id == startup.pk:
                    self.add_error('startup', f'{startup.name} already has a mentoring session from {session.start_time:%H:%M} for this period.')
                break
        return cleaned


class ParticipantJourneyForm(forms.ModelForm):
    change_note = forms.CharField(
        required=False, label='Stage/status change note',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Optional reason, handoff, or review note for this change'}),
    )

    class Meta:
        model = ParticipantJourney
        fields = ['participant_name', 'email', 'phone', 'startup', 'current_stage', 'status', 'cohort', 'started_on', 'assigned_to', 'internal_notes']
        widgets = {
            'participant_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'startup': forms.Select(attrs={'class': 'form-select'}),
            'current_stage': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'cohort': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. BUNI 2026 Cohort 1'}),
            'started_on': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['startup'].required = False
        self.fields['startup'].queryset = Startup.objects.order_by('name')
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(profile__user_type__in=('staff', 'admin'))).distinct().order_by('username')
        self.fields['assigned_to'].label = 'Journey owner'
        self.fields['internal_notes'].help_text = 'Keep internal and avoid sensitive personal information.'
        self.order_fields(['participant_name', 'email', 'phone', 'startup', 'current_stage', 'status', 'cohort', 'started_on', 'assigned_to', 'change_note', 'internal_notes'])


class ParticipantSupportForm(forms.ModelForm):
    class Meta:
        model = ParticipantSupport
        fields = ['support_type', 'title', 'delivered_on', 'provider', 'hours', 'notes']
        widgets = {
            'support_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'delivered_on': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'provider': forms.TextInput(attrs={'class': 'form-input'}),
            'hours': forms.NumberInput(attrs={'class': 'form-input', 'min': '0', 'step': '0.25'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        }

    def clean_hours(self):
        hours = self.cleaned_data.get('hours')
        if hours is not None and hours <= 0:
            raise forms.ValidationError('Hours must be greater than zero.')
        return hours


class ParticipantFollowUpForm(forms.ModelForm):
    class Meta:
        model = ParticipantFollowUp
        fields = ['action', 'due_date', 'assigned_to', 'mentor', 'mentor_session', 'notes']
        widgets = {
            'action': forms.TextInput(attrs={'class': 'form-input'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'mentor': forms.Select(attrs={'class': 'form-select'}),
            'mentor_session': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        }

    def __init__(self, *args, journey=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.journey = journey or getattr(self.instance, 'journey', None)
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(profile__user_type__in=('staff', 'admin'))).distinct().order_by('username')
        self.fields['mentor'].required = False
        self.fields['mentor'].queryset = Mentor.objects.filter(is_active=True).order_by('name')
        self.fields['mentor_session'].required = False
        sessions = MentorEngagement.objects.none()
        if self.journey and self.journey.startup_id:
            sessions = MentorEngagement.objects.filter(startup_id=self.journey.startup_id).select_related('mentor').order_by('-date')
        self.fields['mentor_session'].queryset = sessions
        if self.journey:
            self.instance.journey = self.journey


class ParticipantOutcomeForm(forms.ModelForm):
    class Meta:
        model = ParticipantOutcome
        fields = ['recorded_on', 'full_time_jobs', 'part_time_jobs', 'monthly_revenue', 'revenue_currency', 'customers_or_users', 'milestone', 'notes']
        widgets = {
            'recorded_on': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'full_time_jobs': forms.NumberInput(attrs={'class': 'form-input', 'min': '0'}),
            'part_time_jobs': forms.NumberInput(attrs={'class': 'form-input', 'min': '0'}),
            'monthly_revenue': forms.NumberInput(attrs={'class': 'form-input', 'min': '0', 'step': '0.01'}),
            'revenue_currency': forms.TextInput(attrs={'class': 'form-input', 'maxlength': '3'}),
            'customers_or_users': forms.NumberInput(attrs={'class': 'form-input', 'min': '0'}),
            'milestone': forms.TextInput(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        }

    def clean_revenue_currency(self):
        currency = self.cleaned_data['revenue_currency'].strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise forms.ValidationError('Enter a three-letter currency code, such as TZS or USD.')
        return currency
