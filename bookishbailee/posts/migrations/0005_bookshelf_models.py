from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0004_seed_categories'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookshelfEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('author', models.CharField(blank=True, max_length=120)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'bookshelf entries',
                'ordering': ('order', 'title'),
            },
        ),
        migrations.CreateModel(
            name='RightNowFeature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_title', models.CharField(blank=True, max_length=200)),
                ('note', models.CharField(blank=True, max_length=280)),
                ('label', models.CharField(default='currently re-reading', max_length=120)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Right Now feature',
                'verbose_name_plural': 'Right Now feature',
            },
        ),
    ]
