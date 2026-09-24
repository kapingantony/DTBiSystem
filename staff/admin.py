from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    DataImportBatch, Investor, Mentor, MentorEngagement, PageVisit,
    Startup, StartupStatusHistory, UserProfile,
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
    list_display = ('mentor', 'startup', 'date', 'hours')
    list_filter = ('date',)
    search_fields = ('mentor__name', 'startup__name', 'topics', 'outcome')


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
