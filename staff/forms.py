from django import forms
from .models import (
    Startup, Founder, Opportunity, Funding,
    KPI, PitchDeck, ServiceOffered, Partnership
)


class StartupForm(forms.ModelForm):
    class Meta:
        model = Startup
        fields = [
            'name', 'startup_type', 'description', 'industry', 'website',
            'logo', 'cover_image', 'founded_date', 'incubation_start',
            'incubation_end', 'year_incubated', 'contract_status', 'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Startup name'}),
            'startup_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Brief description of the startup...'}),
            'industry': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Fintech, AgriTech'}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
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
        fields = ['source', 'amount', 'funding_type', 'date_received', 'status', 'notes']
        widgets = {
            'source': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Investor or fund name'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00'}),
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
    class Meta:
        model = Partnership
        fields = [
            'startup_name', 'contact_name', 'email', 'phone',
            'organization', 'partnership_type', 'message'
        ]
        widgets = {
            'startup_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your startup or company name'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'organization': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Organization (if any)'}),
            'partnership_type': forms.Select(attrs={'class': 'form-select'}),
            'message': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Tell us about the partnership you have in mind...'}),
        }
