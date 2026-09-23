
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from staff.views import user_login, user_logout, dashboard, index, landing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing, name='landing'),
    path('staff/', include('staff.urls')),
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='landing'), name='logout'),
]
