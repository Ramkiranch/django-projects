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
    md = markdown.Markdown(
        extensions=_POST_DETAIL_EXTENSIONS,
        output_format='html5',
    )
    body_html = md.convert(post.body or '')
    h2_count = sum(1 for tok in md.toc_tokens if tok.get('level') == 2)
    show_toc = h2_count >= TOC_MIN_H2

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
            'recommended_posts': recommended_posts,
        },
    )
