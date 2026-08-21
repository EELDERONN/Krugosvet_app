from django.urls import path

from . import views


urlpatterns = [
    path('', views.index, name='home'),
    path('tours/', views.tours, name='tours'),
    path('about/', views.about, name='about'),

    # вход / выход
    path('auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),

    # личный кабинет
    path('account/', views.account, name='account'),
    path('account/delete/', views.account_delete, name='account_delete'),

    # действия внутри кабинета (fetch из account.js)
    path('favorites/<int:tour_id>/toggle/', views.favorite_toggle, name='favorite_toggle'),
    path('notifications/read-all/', views.notifications_read, name='notifications_read'),
    path('notifications/<int:pk>/read/', views.notification_read, name='notification_read'),
]
