"""Post admin with a "Share URLs" panel.

The panel renders ready-to-paste URLs tagged with UTM parameters for
each platform Ram cross-posts to. Eliminates typo risk and the
"did I tag that one?" mental load when scheduling shares.

Convention (kept minimal — see the discussion in the foundations PR):
  utm_source = linkedin / twitter / instagram / facebook / newsletter
  utm_medium = social  (for social platforms) or email  (for newsletter)
  utm_campaign = (intentionally omitted by default; add per-share when
                  promoting the same post twice or running a series)
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import Post

PLATFORMS = [
    ('LinkedIn',  'linkedin',  'social'),
    ('Twitter/X', 'twitter',   'social'),
    ('Instagram', 'instagram', 'social'),
    ('Facebook',  'facebook',  'social'),
    ('Newsletter', 'newsletter', 'email'),
]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'pub_date')
    date_hierarchy = 'pub_date'
    search_fields = ('title', 'body')
    readonly_fields = ('share_urls',)

    fieldsets = (
        (None, {
            'fields': ('title', 'pub_date', 'image', 'body'),
        }),
        ('Share URLs (UTM-tagged for source attribution)', {
            'fields': ('share_urls',),
            'description': (
                'Copy these into your scheduled posts on each platform. '
                'Plausible will show signups + visits broken down by source.'
            ),
        }),
    )

    @admin.display(description='Tracked URLs by platform')
    def share_urls(self, obj):
        if not obj.pk:
            return '(save the post to see share URLs)'

        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')

        def url_for(source: str, medium: str) -> str:
            qs = urlencode({'utm_source': source, 'utm_medium': medium})
            return f'{site_url}/posts/{obj.pk}/?{qs}'

        rows = format_html_join(
            '\n',
            '<tr>'
            '<td style="padding:4px 12px 4px 0;"><strong>{}</strong></td>'
            '<td style="padding:4px 0;"><code style="user-select:all;">{}</code></td>'
            '</tr>',
            ((label, url_for(source, medium)) for label, source, medium in PLATFORMS),
        )
        return format_html(
            '<table style="border-collapse:collapse;font-size:13px;">'
            '<thead><tr>'
            '<th style="text-align:left;padding:4px 12px 8px 0;">Platform</th>'
            '<th style="text-align:left;padding:4px 0 8px;">Tracked URL</th>'
            '</tr></thead>'
            '<tbody>{}</tbody>'
            '</table>'
            '<p style="margin-top:8px;color:#6c757d;font-size:12px;">'
            'Tip: triple-click a URL to select it, then copy.'
            '</p>',
            rows,
        )
