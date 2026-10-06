
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from staff.views import user_login, user_logout, dashboard, index, landing
from staff import views as staff_views
from staff import data_views as staff_data_views
from staff.public_reports import public_report_csv, public_report_pdf

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing, name='landing'),
    path('impact/', staff_views.impact_explorer, name='impact_explorer'),
    path('hub-history/', staff_views.hub_history, name='hub_history'),
    path('mentors/', staff_views.mentors, name='mentors'),
    path('mentors/<int:pk>/', staff_data_views.mentor_profile, name='mentor_profile'),
    path('investors/', staff_views.investors, name='investors'),
    path('investors/<int:pk>/', staff_data_views.investor_profile, name='investor_profile'),
    path('reports/<str:kind>.csv', public_report_csv, name='public_report'),
    path('reports/<str:kind>.pdf', public_report_pdf, name='public_report_pdf'),
    path('staff/', include('staff.urls')),
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='landing'), name='logout'),
    path('accounts/password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        success_url='/accounts/password-reset/done/',
    ), name='password_reset'),
    path('accounts/password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/accounts/reset/complete/',
    ), name='password_reset_confirm'),
    path('accounts/reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
