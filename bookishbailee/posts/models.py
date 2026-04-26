from django.db import models
from django.db.models import Q, UniqueConstraint
from django.urls import reverse
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill


class WebConfig(models.Model):
    """Feature flags and runtime config toggles — one row per flag.

    Each row is read by `posts.context_processors.feature_flags` and
    exposed to templates as `feature_flags.<key>`. Toggle from the
    admin without a redeploy.
    """

    key = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=False)
    description = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'feature flag'
        verbose_name_plural = 'feature flags'
        ordering = ('key',)

    def __str__(self):
        return f'{self.key} ({"on" if self.enabled else "off"})'


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    tagline = models.CharField(
        max_length=200,
        blank=True,
        help_text='Hand-written tagline shown on the About page category tile.',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ('order', 'name')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category_detail', args=[self.slug])


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tag_detail', args=[self.slug])


class Post(models.Model):
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=280, unique=True)
    pub_date = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='posts'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')

    image = models.ImageField(upload_to='posts/')
    caption = models.CharField(
        max_length=160,
        blank=True,
        help_text='Caption shown under the hero image (italic, centered).',
    )
    excerpt = models.CharField(
        max_length=280,
        help_text='Dek shown under the title and used as the meta description.',
    )
    body = models.TextField(
        help_text=(
            'Markdown is supported. Pull quotes use the syntax `> [!quote]` '
            'on the line above the quoted paragraph.'
        ),
    )
    reading_time = models.PositiveIntegerField(default=1, blank=True)
    is_featured = models.BooleanField(default=False)

    image_home_hero = ImageSpecField(
        source='image', processors=[ResizeToFill(600, 800)],
        format='JPEG', options={'quality': 82},
    )
    image_featured = ImageSpecField(
        source='image', processors=[ResizeToFill(1280, 720)],
        format='JPEG', options={'quality': 82},
    )
    image_card = ImageSpecField(
        source='image', processors=[ResizeToFill(480, 600)],
        format='JPEG', options={'quality': 82},
    )
    image_post_hero = ImageSpecField(
        source='image', processors=[ResizeToFill(1600, 800)],
        format='JPEG', options={'quality': 85},
    )
    image_related = ImageSpecField(
        source='image', processors=[ResizeToFill(320, 240)],
        format='JPEG', options={'quality': 82},
    )

    class Meta:
        ordering = ('-pub_date',)
        constraints = [
            UniqueConstraint(
                fields=['is_featured'],
                condition=Q(is_featured=True),
                name='one_featured_post',
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('post_detail', args=[self.slug])

    def pub_date_modified(self):
        return self.pub_date.strftime('%b %e %Y')

    def save(self, *args, **kwargs):
        self.reading_time = self._compute_reading_time()
        super().save(*args, **kwargs)

    def _compute_reading_time(self):
        from .templatetags.markdown_filters import strip_markdown

        words = len(strip_markdown(self.body or '').split())
        return max(1, round(words / 220))
