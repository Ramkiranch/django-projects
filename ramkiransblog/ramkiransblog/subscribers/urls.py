from django.urls import path

from . import views

urlpatterns = [
    path('subscribe/', views.subscribe, name='subscribe'),
    path('subscribe/confirm/<str:token>/', views.confirm, name='subscribe_confirm'),
    path('subscribe/unsubscribe/<str:token>/', views.unsubscribe, name='subscribe_unsubscribe'),
]
