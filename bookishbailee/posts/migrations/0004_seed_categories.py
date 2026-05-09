"""Seed the starter categories so a fresh deploy has them after migrate.

Idempotent — uses get_or_create keyed on `slug`, so editing names or
taglines via admin after the migration runs won't be reverted.
"""
from django.db import migrations


CATEGORIES = [
    # (slug, name, tagline, order)
    ('reading', 'Reading', 'what i read this month', 1),
    ('notes',   'Notes',   'half-formed thoughts',   2),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('posts', 'Category')
    for slug, name, tagline, order in CATEGORIES:
        Category.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'tagline': tagline, 'order': order},
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model('posts', 'Category')
    Category.objects.filter(slug__in=[s for s, *_ in CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0003_seed_subscriber_flag'),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
