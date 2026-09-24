from django.urls import path
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from . import views
from . import data_views

app_name = 'staff'

urlpatterns = [
    path('visitor-stats/', views.visitor_stats, name='visitor_stats'),
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('register/', views.register, name='register'),
    path('settings/', views.settings_view, name='settings'),
    path(
        'settings/password/',
        PasswordChangeView.as_view(
            template_name='registration/password_change_form.html',
            success_url=reverse_lazy('staff:settings'),
        ),
        name='password_change',
    ),
    path('', views.index, name='dashboard'),
    path('startups/', views.startups, name='startups'),
    path('startups/create/', views.startup_create, name='startup_create'),
    path('startups/<slug:slug>/', views.startup_profile, name='startup_profile'),
    path('partnership/', views.partnership_form, name='partnership_form'),
    path('partnership/success/', views.partnership_success, name='partnership_success'),
    path('mentors/', views.mentors, name='mentors'),
    path('investors/', views.investors, name='investors'),
    path('staff/', views.staff_list, name='staff_list'),
    path('data/', data_views.data_hub, name='data_hub'),
    path('data/imports/', data_views.data_import, name='data_import'),
    path('data/reports/', data_views.data_reports, name='data_reports'),
    path('data/page-visits/', data_views.page_visit_admin, name='page_visit_admin'),
    path('data/partnerships/', data_views.partnership_inbox, name='partnership_inbox'),
    path('mentor-sessions/', data_views.mentor_sessions, name='mentor_sessions'),
    path('data/participant-journey/', data_views.participant_journey, name='participant_journey'),
    path('mentor-sessions/<int:pk>/calendar.ics', data_views.mentor_session_ical, name='mentor_session_ical'),
    path('mentors/<int:pk>/', data_views.mentor_profile, name='mentor_profile'),
    path('investors/<int:pk>/', data_views.investor_profile, name='investor_profile'),
]
