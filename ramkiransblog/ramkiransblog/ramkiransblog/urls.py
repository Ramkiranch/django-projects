"""ramkiransblog URL Configuration

For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
import environ
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

import posts.views
import sitepages.views

env = environ.Env()

urlpatterns = [
    path(env('DJANGO_ADMIN_URL', default='rk-admin/'), admin.site.urls),
    path('', posts.views.home, name='home'),
    path('posts/<int:post_id>/', posts.views.post_details, name='post_detail'),
    path('about/', sitepages.views.about, name='about'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
