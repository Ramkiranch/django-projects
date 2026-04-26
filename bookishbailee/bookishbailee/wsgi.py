"""WSGI config for bookishbailee project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookishbailee.settings')

application = get_wsgi_application()
