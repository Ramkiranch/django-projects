"""ramkiransblog URL Configuration

For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
import environ
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

import posts.views
import sitepages.views
from posts.feeds import PostFeed
from posts.sitemaps import PostSitemap
from sitepages.sitemaps import StaticViewSitemap

env = environ.Env()

sitemaps = {
    'posts': PostSitemap,
    'static': StaticViewSitemap,
}

urlpatterns = [
    path(env('DJANGO_ADMIN_URL', default='rk-admin/'), admin.site.urls),
    path('', posts.views.home, name='home'),
    path('posts/<int:post_id>/', posts.views.post_details, name='post_detail'),
    path('about/', sitepages.views.about, name='about'),

    # SEO + syndication
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', sitepages.views.robots_txt, name='robots'),
    path('feed/', PostFeed(), name='feed'),

    # Email capture
    path('', include('subscribers.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
