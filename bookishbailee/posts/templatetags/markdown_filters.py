"""Markdown rendering for blog post bodies.

Posts are authored by superusers; the rendered HTML is `mark_safe`-d
without bleach sanitization. If untrusted authors are added, swap in
bleach + an allowlist.

Beyond the stock pipeline, three things are wired up here:

- A `pull_quote` block-processor that turns a markdown paragraph
  preceded by `> [!quote]` into an `<aside class="pullquote">`. It
  must run before the standard `BlockQuoteProcessor`.
- A `dropcap` post-process step that wraps the first letter of the
  first paragraph in `<span class="dropcap">`.
- The stock `toc` extension produces `<h2 id=...>` anchors and a
  `.toc` attribute we expose via `render_toc` for the right rail.
"""
import re
from xml.etree import ElementTree as etree

import markdown as md
from django import template
from django.utils.safestring import mark_safe
from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

register = template.Library()


_BASE_EXTENSIONS = ['extra', 'sane_lists', 'smarty', 'toc']


# ─── Pull quote: > [!quote] then a paragraph ───────────────────────────

_PULLQUOTE_MARKER = re.compile(r'^>\s*\[!quote\]\s*$', re.IGNORECASE)


class PullQuoteProcessor(BlockProcessor):
    def test(self, parent, block):
        first_line = block.split('\n', 1)[0]
        return bool(_PULLQUOTE_MARKER.match(first_line))

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.split('\n')
        quote_lines = [line.lstrip('>').strip() for line in lines[1:] if line.strip()]
        text = ' '.join(quote_lines).strip()

        aside = etree.SubElement(parent, 'aside')
        aside.set('class', 'pullquote')
        p = etree.SubElement(aside, 'p')
        p.text = text


class PullQuoteExtension(Extension):
    def extendMarkdown(self, md_instance):
        md_instance.parser.blockprocessors.register(
            PullQuoteProcessor(md_instance.parser),
            'pullquote',
            # Higher priority than blockquote (which is 20) so the
            # `> [!quote]` marker isn't first claimed as a blockquote.
            25,
        )


# ─── Drop cap: wrap the first letter of the first <p> ──────────────────

_FIRST_P = re.compile(r'(<p>)(\s*)([A-Za-z0-9])', re.DOTALL)


def _add_dropcap(html: str) -> str:
    return _FIRST_P.sub(
        lambda m: f'{m.group(1)}{m.group(2)}<span class="dropcap">{m.group(3)}</span>',
        html,
        count=1,
    )


# ─── Filters exposed to templates ──────────────────────────────────────


@register.filter(name='markdown')
def render_markdown(value):
    if not value:
        return ''
    instance = md.Markdown(
        extensions=_BASE_EXTENSIONS + [PullQuoteExtension()],
        output_format='html5',
    )
    html = instance.convert(value)
    html = _add_dropcap(html)
    return mark_safe(html)


@register.filter(name='render_toc')
def render_toc(value):
    """Return just the TOC `<ul>` for the body text (right-rail use)."""
    if not value:
        return ''
    instance = md.Markdown(
        extensions=_BASE_EXTENSIONS + [PullQuoteExtension()],
        output_format='html5',
    )
    instance.convert(value)
    return mark_safe(instance.toc or '')


# ─── Plain-text stripping for previews / reading-time ──────────────────


_MD_STRIP_PATTERNS = [
    (re.compile(r'^#{1,6}\s+', re.MULTILINE), ''),
    (re.compile(r'\*\*([^*]+)\*\*'), r'\1'),
    (re.compile(r'\*([^*]+)\*'), r'\1'),
    (re.compile(r'`([^`]+)`'), r'\1'),
    (re.compile(r'^[-*+]\s+', re.MULTILINE), ''),
    (re.compile(r'^\d+\.\s+', re.MULTILINE), ''),
    (re.compile(r'^>\s?', re.MULTILINE), ''),
    (re.compile(r'!\[([^\]]*)\]\([^)]+\)'), r'\1'),
    (re.compile(r'\[([^\]]+)\]\([^)]+\)'), r'\1'),
]


@register.filter(name='strip_markdown')
def strip_markdown(value):
    if not value:
        return ''
    text = value
    for pattern, replacement in _MD_STRIP_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()
