from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='home'),
    path('tours/', views.tours, name='tours'),
    path('about/', views.about, name='about'),

]