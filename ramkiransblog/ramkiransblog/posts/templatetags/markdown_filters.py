"""Markdown rendering for blog post bodies.

Why a custom filter and not django-markdownx / similar?
- We only need read-side rendering (admin write side stays plain TextField).
- The `markdown` library is pure-Python and dependency-light.
- Posts are only authored by superusers, so input is trusted; we mark
  the rendered HTML as safe without bleach sanitization. If untrusted
  authors are ever added, swap in bleach + an allowlist.
"""
import re

import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Extensions worth turning on for a tech-leaning blog:
# - extra: tables, fenced code blocks, footnotes, definition lists, attr_list
# - sane_lists: don't promote a `1.` mid-paragraph into a numbered list
# - smarty: typographic quotes / em-dashes
_EXTENSIONS = ['extra', 'sane_lists', 'smarty']


@register.filter(name='markdown')
def render_markdown(value):
    """Render a Markdown string to HTML and mark it safe.

    Usage in templates:
        {% load markdown_filters %}
        {{ post.body|markdown }}
    """
    if not value:
        return ''
    html = md.markdown(value, extensions=_EXTENSIONS, output_format='html5')
    return mark_safe(html)


# Strip the most common Markdown syntax characters so the home-page card
# preview doesn't show literal `##`, `**`, `_`, ``` etc.
_MD_STRIP_PATTERNS = [
    (re.compile(r'^#{1,6}\s+', re.MULTILINE), ''),   # ATX headings
    (re.compile(r'\*\*([^*]+)\*\*'), r'\1'),         # bold
    (re.compile(r'\*([^*]+)\*'), r'\1'),             # italic
    (re.compile(r'`([^`]+)`'), r'\1'),               # inline code
    (re.compile(r'^[-*+]\s+', re.MULTILINE), ''),    # bullet lists
    (re.compile(r'^\d+\.\s+', re.MULTILINE), ''),    # numbered lists
    (re.compile(r'^>\s?', re.MULTILINE), ''),        # blockquote markers
    (re.compile(r'!\[([^\]]*)\]\([^)]+\)'), r'\1'),  # images -> alt text
    (re.compile(r'\[([^\]]+)\]\([^)]+\)'), r'\1'),   # links -> link text
]


@register.filter(name='strip_markdown')
def strip_markdown(value):
    """Best-effort Markdown stripping for short previews. Not a full parser."""
    if not value:
        return ''
    text = value
    for pattern, replacement in _MD_STRIP_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()
