from django.contrib import admin

from .models import Investor, Mentor, Startup, UserProfile


@admin.action(description='Approve selected startups')
def approve_startups(modeladmin, request, queryset):
    queryset.update(status='active')


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
