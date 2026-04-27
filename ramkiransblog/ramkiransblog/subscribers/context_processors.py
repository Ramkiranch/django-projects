"""Site-wide template context.

Exposes a SubscribeForm instance + site identity to every template so
the footer signup partial works everywhere without each view having
to construct it.
"""
from django.conf import settings

from .forms import SubscribeForm


def site_globals(request):
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', "Ramkiran's Blog"),
        'SITE_AUTHOR': getattr(settings, 'SITE_AUTHOR', 'Ram Chevendra'),
        'subscribe_form': SubscribeForm(),
    }
