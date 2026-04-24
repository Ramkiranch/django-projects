from django.db import models


class Post(models.Model):
    title = models.CharField(max_length=250)
    pub_date = models.DateTimeField()
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

    def summary(self):
        """Plain-text preview for cards. Strips Markdown syntax and truncates."""
        from .templatetags.markdown_filters import strip_markdown

        plain = strip_markdown(self.body)
        return plain[:160]
