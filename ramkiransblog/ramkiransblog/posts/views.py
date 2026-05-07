import html as html_lib
import re
import unicodedata

import markdown
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Post

POSTS_PER_PAGE = 5
RECOMMENDED_COUNT = 3
# Min number of H2 headings before we render the TOC sidebar. Posts with
# 0 or 1 sections don't need (and look odd with) a navigation sidebar.
TOC_MIN_H2 = 2

# Markdown extensions used for the post-detail body. Same set the
# `|markdown` template filter uses, plus `toc` to populate
# Markdown.toc / Markdown.toc_tokens for the sidebar.
_POST_DETAIL_EXTENSIONS = ['extra', 'sane_lists', 'smarty', 'toc']


# Authors often write `# Title` at the top of their markdown body even
# though Post.title is already rendered as the page <h1> in the post
# hero. Without this strip the page shows the title twice (once as the
# big hero h1, once as a giant body h1).
_LEADING_H1_RE = re.compile(r'\s*<h1[^>]*>(.*?)</h1>\s*', re.DOTALL)


def _normalize_for_title_match(s: str) -> str:
    """Aggressive normalization so 'multi-agentic' matches 'multi agentic',
    'What's' matches 'What’s', etc. Strips HTML tags, decodes entities,
    folds smart-typography back to ASCII, lowercases, collapses whitespace,
    drops punctuation."""
    s = re.sub(r'<[^>]+>', '', s)             # strip nested tags
    s = html_lib.unescape(s)                  # &amp; → &, &lcub; → {, etc.
    s = unicodedata.normalize('NFKD', s)
    s = s.replace('’', "'").replace('‘', "'")
    s = s.replace('“', '"').replace('”', '"')
    s = s.replace('—', '-').replace('–', '-')
    s = re.sub(r'[^\w\s]', ' ', s)            # strip punctuation
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def _strip_leading_title_h1(body_html: str, title: str) -> str:
    """If body_html begins with an <h1> whose text (normalized) matches
    the post title, drop that h1. Avoids the duplicate-title visual bug.
    """
    m = _LEADING_H1_RE.match(body_html)
    if not m:
        return body_html
    if _normalize_for_title_match(m.group(1)) == _normalize_for_title_match(title):
        return body_html[m.end():]
    return body_html


def home(request):
    posts_qs = Post.objects.order_by('-pub_date')
    paginator = Paginator(posts_qs, POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    elided_range = paginator.get_elided_page_range(
        page_obj.number, on_each_side=2, on_ends=1
    )
    return render(
        request,
        'posts/home.html',
        {'page_obj': page_obj, 'elided_range': elided_range},
    )


def post_details(request, post_id):
    post = get_object_or_404(Post, pk=post_id)

    # Render the body via a Markdown INSTANCE (not the module-level
    # markdown.markdown function) so we can inspect .toc / .toc_tokens
    # after conversion. This is the only place we need TOC info; the
    # |markdown template filter and the RSS feed continue to use the
    # simpler module-level function.
    # toc_depth='2-6' tells the toc extension to skip H1 entirely. Authors
    # often write `# Title` at the top of the body even though Post.title
    # already renders as the page H1; without this the H1 becomes the root
    # of the toc tree and all H2s nest under it as children. Two bad effects:
    # (1) `sum(... level == 2)` over the top-level tokens counts 0 H2s and
    # `show_toc` evaluates to False (the TOC sidebar disappears),
    # (2) the rendered TOC sidebar shows the post title as a top-level entry
    # with sections indented underneath, which doesn't match other posts.
    md = markdown.Markdown(
        extensions=_POST_DETAIL_EXTENSIONS,
        extension_configs={'toc': {'toc_depth': '2-6'}},
        output_format='html5',
    )
    body_html = md.convert(post.body or '')
    body_html = _strip_leading_title_h1(body_html, post.title)
    h2_count = sum(1 for tok in md.toc_tokens if tok.get('level') == 2)
    show_toc = h2_count >= TOC_MIN_H2

    # `extra` extension's fenced_code emits ```mermaid blocks as
    # <pre><code class="language-mermaid">…</code></pre>. We detect that
    # marker server-side and only load the Mermaid client library on
    # posts that actually contain a diagram (saves ~600 KB on every
    # other post-detail page view).
    has_mermaid = 'class="language-mermaid"' in body_html

    recommended_posts = (
        Post.objects.exclude(pk=post.pk)
        .order_by('-pub_date')[:RECOMMENDED_COUNT]
    )

    return render(
        request,
        'posts/posts_detail.html',
        {
            'post': post,
            'body_html': body_html,
            'toc_html': md.toc if show_toc else '',
            'show_toc': show_toc,
            'has_mermaid': has_mermaid,
            'recommended_posts': recommended_posts,
        },
    )
