"""Seed the `show_subscriber_content` feature flag (default: disabled).

Idempotent — uses get_or_create so re-running this migration on a
database where the flag was manually toggled won't reset it.
"""
from django.db import migrations


SHOW_SUBSCRIBER_CONTENT = 'show_subscriber_content'


def seed_flag(apps, schema_editor):
    WebConfig = apps.get_model('posts', 'WebConfig')
    WebConfig.objects.get_or_create(
        key=SHOW_SUBSCRIBER_CONTENT,
        defaults={
            'enabled': False,
            'description': (
                'Show the newsletter band on the home page and the '
                'Subscribe links in the nav and footer.'
            ),
        },
    )


def remove_flag(apps, schema_editor):
    WebConfig = apps.get_model('posts', 'WebConfig')
    WebConfig.objects.filter(key=SHOW_SUBSCRIBER_CONTENT).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0002_webconfig'),
    ]

    operations = [
        migrations.RunPython(seed_flag, remove_flag),
    ]
