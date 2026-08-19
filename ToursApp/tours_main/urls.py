from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='home'),
    path('tours/', views.tours, name='tours'),
    path('about/', views.about, name='about'),
    path('auth/', views.auth_view, name='auth'),
    path('account/', views.account, name='account'),
    path('logout/', views.logout_view, name='logout'),
]