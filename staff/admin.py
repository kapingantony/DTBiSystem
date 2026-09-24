from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    DataImportBatch, Investor, Mentor, MentorEngagement, MentorEngagementHistory, PageVisit,
    Partnership, PartnershipHistory, Startup, StartupStatusHistory, UserProfile,
    ParticipantJourney, ParticipantJourneyHistory, ParticipantSupport,
    ParticipantFollowUp, ParticipantFollowUpHistory, ParticipantOutcome,
)


class StaffAccountAdmin(UserAdmin):
    """Create regular staff accounts by default from Django Admin."""

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_staff = True
            obj.is_superuser = False
        super().save_model(request, obj, form, change)


admin.site.unregister(User)
admin.site.register(User, StaffAccountAdmin)


@admin.action(description='Approve selected startups')
def approve_startups(modeladmin, request, queryset):
    for startup in queryset.iterator():
        startup.status = 'active'
        startup.save(update_fields=['status', 'updated_at'])


@admin.register(Startup)
class StartupAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'status', 'directory_visible', 'source', 'updated_at')
    list_filter = ('status', 'startup_type', 'contract_status', 'directory_visible', 'source')
    search_fields = ('name', 'description', 'industry', 'contact_email', 'phone')
    actions = (approve_startups, 'delete_selected')
    readonly_fields = ('slug', 'profile_completion', 'created_at', 'updated_at')
    fieldsets = (
        ('BUNI startup information', {
            'fields': ('name', 'startup_type', 'description', 'industry', 'website', 'contact_email', 'phone', 'source')
        }),
        ('Approval and programme status', {
            'fields': ('status', 'contract_status', 'profile_completion', 'directory_visible', 'year_incubated')
        }),
        ('Dates and media', {
            'fields': ('founded_date', 'incubation_start', 'incubation_end', 'logo', 'cover_image')
        }),
        ('System fields', {'fields': ('slug', 'created_at', 'updated_at')}),
    )


@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'role', 'education_level', 'is_active', 'source')
    list_filter = ('is_active', 'source')
    search_fields = ('name', 'email', 'role', 'skills', 'training_topics')


@admin.register(Investor)
class InvestorAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'email', 'investment_interest', 'status', 'source')
    list_filter = ('status', 'source')
    search_fields = ('name', 'organization', 'email', 'investment_interest')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'startup', 'company_name', 'registration_date')
    list_filter = ('user_type', 'registration_date')
    search_fields = ('user__username', 'user__email', 'company_name')
    fieldsets = (
        ('Account', {'fields': ('user', 'user_type')}),
        ('Startup', {'fields': ('startup', 'company_name', 'bio')}),
        ('Contact', {'fields': ('phone', 'company_website', 'email_notifications', 'theme')}),
    )


@admin.register(MentorEngagement)
class MentorEngagementAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'startup', 'date', 'start_time', 'hours', 'status')
    list_filter = ('status', 'date', 'mentor')
    search_fields = ('mentor__name', 'startup__name', 'topics', 'outcome', 'meeting_location')
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = MentorEngagement.objects.filter(pk=obj.pk).values('status', 'date', 'start_time').first()
        super().save_model(request, obj, form, change)
        if previous is None or any(previous[key] != getattr(obj, key) for key in ('status', 'date', 'start_time')):
            MentorEngagementHistory.objects.create(
                engagement=obj,
                old_status=previous['status'] if previous else '',
                new_status=obj.status,
                old_date=previous['date'] if previous else None,
                new_date=obj.date,
                old_start_time=previous['start_time'] if previous else None,
                new_start_time=obj.start_time,
                changed_by=request.user,
                note=obj.outcome if change else 'Session scheduled in admin.',
            )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'mentor':
            kwargs['queryset'] = Mentor.objects.filter(is_active=True)
        if db_field.name == 'startup':
            kwargs['queryset'] = Startup.objects.filter(status='active')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MentorEngagementHistory)
class MentorEngagementHistoryAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'old_status', 'new_status', 'old_date', 'new_date', 'changed_by', 'changed_at')
    list_filter = ('new_status', 'changed_at')
    search_fields = ('engagement__mentor__name', 'engagement__startup__name', 'note')
    readonly_fields = ('engagement', 'old_status', 'new_status', 'old_date', 'new_date', 'old_start_time', 'new_start_time', 'changed_by', 'note', 'changed_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PageVisit)
class PageVisitAdmin(admin.ModelAdmin):
    list_display = ('page_type', 'display_name', 'visit_date', 'visited_at', 'visitor', 'is_read')
    list_filter = ('page_type', 'visit_date', 'is_read')
    search_fields = ('display_name', 'object_key', 'visitor__username')
    readonly_fields = ('page_type', 'object_key', 'display_name', 'session_key', 'visitor', 'visit_date', 'visited_at')


@admin.register(StartupStatusHistory)
class StartupStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('startup', 'status', 'contract_status', 'recorded_at')
    list_filter = ('status', 'contract_status', 'recorded_at')
    search_fields = ('startup__name',)
    readonly_fields = ('startup', 'status', 'contract_status', 'recorded_at')


@admin.register(DataImportBatch)
class DataImportBatchAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'dataset', 'status', 'created_count', 'updated_count', 'skipped_count', 'uploaded_by', 'created_at')
    list_filter = ('dataset', 'status', 'created_at')
    search_fields = ('original_filename', 'uploaded_by__username')
    fields = ('dataset', 'original_filename', 'uploaded_by', 'status', 'headers', 'field_mapping', 'total_rows', 'created_count', 'updated_count', 'skipped_count', 'row_errors', 'created_at', 'completed_at')
    readonly_fields = fields


@admin.register(Partnership)
class PartnershipAdmin(admin.ModelAdmin):
    list_display = ('startup_name', 'organization', 'partnership_type', 'status', 'assigned_to', 'created_at', 'updated_at')
    list_filter = ('status', 'partnership_type', 'created_at')
    search_fields = ('startup_name', 'organization', 'contact_name', 'email', 'related_startup__name')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('related_startup', 'assigned_to')

    def save_model(self, request, obj, form, change):
        previous_status = Partnership.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else ''
        super().save_model(request, obj, form, change)
        if not change or previous_status != obj.status:
            PartnershipHistory.objects.create(
                partnership=obj,
                old_status=previous_status or '',
                new_status=obj.status,
                changed_by=request.user,
                note=obj.review_notes if change else 'Request created in admin.',
            )


@admin.register(PartnershipHistory)
class PartnershipHistoryAdmin(admin.ModelAdmin):
    list_display = ('partnership', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status', 'changed_at')
    search_fields = ('partnership__startup_name', 'partnership__organization', 'note')
    readonly_fields = ('partnership', 'old_status', 'new_status', 'changed_by', 'note', 'changed_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ParticipantJourney)
class ParticipantJourneyAdmin(admin.ModelAdmin):
    list_display = ('participant_name', 'startup', 'current_stage', 'status', 'cohort', 'assigned_to', 'updated_at')
    list_filter = ('current_stage', 'status', 'cohort')
    search_fields = ('participant_name', 'email', 'startup__name', 'cohort')
    list_select_related = ('startup', 'assigned_to')

    def save_model(self, request, obj, form, change):
        previous = ParticipantJourney.objects.filter(pk=obj.pk).values('current_stage', 'status').first() if change else None
        super().save_model(request, obj, form, change)
        if previous is None or previous['current_stage'] != obj.current_stage or previous['status'] != obj.status:
            ParticipantJourneyHistory.objects.create(
                journey=obj, old_stage=previous['current_stage'] if previous else '',
                new_stage=obj.current_stage, old_status=previous['status'] if previous else '',
                new_status=obj.status, changed_by=request.user,
                note='Journey created in admin.' if previous is None else 'Journey stage/status updated in admin.',
            )


@admin.register(ParticipantJourneyHistory)
class ParticipantJourneyHistoryAdmin(admin.ModelAdmin):
    list_display = ('journey', 'old_stage', 'new_stage', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_stage', 'new_status', 'changed_at')
    search_fields = ('journey__participant_name', 'journey__startup__name', 'note')
    readonly_fields = ('journey', 'old_stage', 'new_stage', 'old_status', 'new_status', 'changed_by', 'note', 'changed_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ParticipantSupport)
class ParticipantSupportAdmin(admin.ModelAdmin):
    list_display = ('journey', 'support_type', 'title', 'delivered_on', 'provider', 'hours')
    list_filter = ('support_type', 'delivered_on')
    search_fields = ('journey__participant_name', 'journey__startup__name', 'title', 'provider')


@admin.register(ParticipantFollowUp)
class ParticipantFollowUpAdmin(admin.ModelAdmin):
    list_display = ('action', 'journey', 'due_date', 'status', 'assigned_to', 'mentor')
    list_filter = ('status', 'due_date')
    search_fields = ('action', 'journey__participant_name', 'journey__startup__name', 'mentor__name')

    def save_model(self, request, obj, form, change):
        previous = ParticipantFollowUp.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if previous is None or previous != obj.status:
            ParticipantFollowUpHistory.objects.create(
                follow_up=obj, old_status=previous or '', new_status=obj.status,
                changed_by=request.user, note='Follow-up created or updated in admin.',
            )


@admin.register(ParticipantFollowUpHistory)
class ParticipantFollowUpHistoryAdmin(admin.ModelAdmin):
    list_display = ('follow_up', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status', 'changed_at')
    search_fields = ('follow_up__action', 'follow_up__journey__participant_name', 'note')
    readonly_fields = ('follow_up', 'old_status', 'new_status', 'changed_by', 'note', 'changed_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ParticipantOutcome)
class ParticipantOutcomeAdmin(admin.ModelAdmin):
    list_display = ('journey', 'recorded_on', 'full_time_jobs', 'part_time_jobs', 'monthly_revenue', 'revenue_currency', 'customers_or_users')
    list_filter = ('recorded_on', 'revenue_currency')
    search_fields = ('journey__participant_name', 'journey__startup__name', 'milestone')
