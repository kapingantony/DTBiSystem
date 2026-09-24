from django.contrib import admin

from .models import UserProfile


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
