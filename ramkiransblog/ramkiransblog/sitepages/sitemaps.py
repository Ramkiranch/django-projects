"""Sitemap entries for the static (non-Post) pages: home and about."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        # Returns (url_name, priority) so we can vary priority per page
        return [
            ('home', 1.0),
            ('about', 0.6),
        ]

    def priority(self, item):
        return item[1]

    def location(self, item):
        return reverse(item[0])
