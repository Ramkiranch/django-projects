import environ
from django.conf import settings
from django.shortcuts import render

env = environ.Env()


def about(request):
    return render(request, 'sitepages/about.html')


def robots_txt(request):
    """Serve /robots.txt with the dynamic admin path Disallow line."""
    context = {
        'admin_path': env('DJANGO_ADMIN_URL', default='rk-admin/'),
        'site_url': getattr(settings, 'SITE_URL', request.build_absolute_uri('/').rstrip('/')),
    }
    return render(request, 'robots.txt', context, content_type='text/plain')
