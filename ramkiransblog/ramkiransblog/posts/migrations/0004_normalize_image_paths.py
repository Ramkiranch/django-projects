"""Strip the legacy ``media/`` prefix from existing Post.image values.

The original model used ``upload_to='media/'`` against a misconfigured
``MEDIA_ROOT = BASE_DIR``, so DB rows store paths like ``media/rk5.png``.
Now that ``MEDIA_ROOT`` is ``BASE_DIR / 'media'`` and ``upload_to='posts/'``,
this one-shot migration normalizes any legacy paths to the new layout.
The actual file move from ``<media>/<file>`` to ``<media>/posts/<file>`` is
handled outside migrations as part of the cutover.
"""
from django.db import migrations


def strip_media_prefix(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    for post in Post.objects.all():
        name = post.image.name
        if name.startswith('media/'):
            new_name = 'posts/' + name[len('media/'):]
        elif not name.startswith('posts/'):
            new_name = 'posts/' + name
        else:
            continue
        post.image.name = new_name
        post.save(update_fields=['image'])


def restore_media_prefix(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    for post in Post.objects.all():
        name = post.image.name
        if name.startswith('posts/'):
            post.image.name = 'media/' + name[len('posts/'):]
            post.save(update_fields=['image'])


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0003_alter_post_image'),
    ]

    operations = [
        migrations.RunPython(strip_media_prefix, restore_media_prefix),
    ]
