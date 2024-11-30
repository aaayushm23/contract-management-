from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from contracts import views

urlpatterns = [
    path('admin/', admin.site.urls),  # Django admin interface
    path('accounts/login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),  # Login page
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),  # Logout functionality
    path('accounts/signup/', include('contracts.urls')),  # Signup functionality (handled in contracts.urls)
    path('contracts/', include('contracts.urls')),  # Include contracts app URLs
    path('', views.landing_page, name='landing_page'), 
]
