from django.urls import path
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from . import views

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
]
