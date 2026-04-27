"""RSS feed for blog posts.

Built on django.contrib.syndication.views.Feed (zero extra deps).
The body is rendered through the existing markdown filter so feed
readers see the full formatted content, not raw markdown.
"""
from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy

from .models import Post
from .templatetags.markdown_filters import render_markdown


class PostFeed(Feed):
    title = "Ramkiran's Blog"
    link = reverse_lazy('home')
    description = (
        'Engineering leadership, AI in the enterprise, and the long game. '
        'Notes from Ram Chevendra, a Senior Software Engineering Manager in fintech.'
    )

    def items(self):
        # Cap at 20 — feed readers don't need the full archive
        return Post.objects.order_by('-pub_date')[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        # Full rendered HTML so readers like Feedly show the whole post
        return render_markdown(item.body)

    def item_link(self, item):
        return reverse_lazy('post_detail', args=[item.id])

    def item_pubdate(self, item):
        return item.pub_date

    def item_author_name(self, item):
        return 'Ram Chevendra'
