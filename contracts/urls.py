from django.urls import path
from . import views
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_contract, name='upload_contract'),
    path('details/<int:pk>/', views.contract_details, name='contract_details'),  # New detail view
    path('signup/', views.signup, name='signup'),
    path('login/', LoginView.as_view(template_name='auth/login.html'), name='login'), 
    path('details/<int:pk>/review/', views.review_contract, name='review_contract'),
    path('delete/<int:pk>/', views.delete_contract, name='delete_contract'),  # New URL pattern
]
