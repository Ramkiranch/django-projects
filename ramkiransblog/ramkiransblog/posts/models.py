import math

from django.db import models

# Avg adult reading speed for technical prose, words/minute. Lower than
# fiction (~250) because EM/AI posts have headings, lists, and code that
# slow you down. Tweakable later if Plausible engagement metrics suggest
# the estimate is off.
WORDS_PER_MINUTE = 225


class Post(models.Model):
    CATEGORY_TECH = 'tech'
    CATEGORY_PERSONAL = 'personal'
    CATEGORY_LEADERSHIP = 'leadership'
    CATEGORY_CHOICES = [
        (CATEGORY_TECH, 'Tech'),
        (CATEGORY_PERSONAL, 'Personal'),
        (CATEGORY_LEADERSHIP, 'Leadership'),
    ]

    title = models.CharField(max_length=250)
    pub_date = models.DateTimeField()
    # Drives which listing page (/, /personal/, /leadership/) the post
    # appears on, and scopes the "More from the blog" recommendations
    # on the detail page. Indexed because every listing query filters on it.
    category = models.CharField(
        max_length=16,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_TECH,
        db_index=True,
    )
    image = models.ImageField(upload_to='posts/')
    body = models.TextField(
        help_text=(
            'Markdown is supported: '
            '## subheading, **bold**, *italic*, '
            '1. numbered lists, - bulleted lists, '
            '[link text](https://example.com), `inline code`, '
            '> blockquote. Leave a blank line between paragraphs.'
        ),
    )

    def __str__(self):
        return self.title

    def pub_date_modified(self):
        return self.pub_date.strftime('%b %e %Y')

    def read_time(self) -> int:
        """Estimated reading time in minutes (rounded up, min 1).

        Strips Markdown syntax first so '**bold**' counts as one word, not
        three. Reuses the same strip_markdown helper as summary().
        """
        from .templatetags.markdown_filters import strip_markdown

        plain = strip_markdown(self.body or '')
        words = len(plain.split())
        return max(1, math.ceil(words / WORDS_PER_MINUTE))

    def summary(self):
        """Plain-text preview for cards.

        Skips the leading "All views are mine..." disclaimer (rendered as a
        blockquote at the top of every post) so the home-page card preview
        shows the actual first sentence of content, not the same disclaimer
        repeated on every card. Specifically: skip leading blank lines,
        blockquote lines (`> ...`), and horizontal rules (`---`, `***`,
        `___`) until we find real prose.
        """
        from .templatetags.markdown_filters import strip_markdown

        lines = self.body.splitlines()
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            is_skippable = (
                not stripped                         # blank line
                or stripped.startswith('>')          # blockquote
                or stripped in ('---', '***', '___') # horizontal rule
            )
            if not is_skippable:
                break
            i += 1
        body_after_disclaimer = '\n'.join(lines[i:])
        plain = strip_markdown(body_after_disclaimer)
        return plain[:160]
