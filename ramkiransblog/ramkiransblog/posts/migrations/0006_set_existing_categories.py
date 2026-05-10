# Data migration: assign categories to the 7 posts that existed before
# the category field landed. The schema migration (0005) gave every row
# the default 'tech' value; this promotes the two non-tech posts to
# their actual categories so /personal/ and /leadership/ aren't empty
# on first deploy.
#
# Filter-update is idempotent: if the row doesn't exist (fresh test DB
# or after a manual delete) the update is a no-op rather than an error,
# so this migration is safe to run anywhere.

from django.db import migrations

CATEGORY_BY_POST_ID = {
    1: 'personal',
    4: 'leadership',
}


def set_categories(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    for pk, category in CATEGORY_BY_POST_ID.items():
        Post.objects.filter(pk=pk).update(category=category)


def revert_categories(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    Post.objects.filter(pk__in=CATEGORY_BY_POST_ID).update(category='tech')


class Migration(migrations.Migration):
    dependencies = [
        ('posts', '0005_post_category_alter_post_body'),
    ]

    operations = [
        migrations.RunPython(set_categories, revert_categories),
    ]
