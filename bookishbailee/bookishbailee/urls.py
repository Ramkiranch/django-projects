"""bookishbailee URL configuration."""
import environ
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

import sitepages.views

env = environ.Env()

urlpatterns = [
    path(env('DJANGO_ADMIN_URL', default='bb-admin/'), admin.site.urls),
    path('about/', sitepages.views.about, name='about'),
    path('', include('posts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
