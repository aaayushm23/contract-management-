from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_contract, name='upload_contract'),
    path('details/<int:pk>/', views.contract_details, name='contract_details'),  # New detail view
    path('signup/', views.signup, name='signup'),
    path('login/', views.signup, name='login'),
]
