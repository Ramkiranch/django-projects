"""Sitemap for blog posts.

Used by django.contrib.sitemaps to generate /sitemap.xml entries that
search engines crawl. We avoid django.contrib.sites here (which would
require a migration + manual SITE_ID config) by relying on the request
to determine the host — Sitemap.get_urls() uses request.scheme + host
when the framework is wired without `sites`.
"""
from django.contrib.sitemaps import Sitemap

from .models import Post


class PostSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.order_by('-pub_date')

    def lastmod(self, obj):
        return obj.pub_date

    def location(self, obj):
        return f'/posts/{obj.id}/'
