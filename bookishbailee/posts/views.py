from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import BookshelfEntry, Category, Post, RightNowFeature, Tag

POSTS_PER_PAGE = 9


def home(request):
    featured = Post.objects.filter(is_featured=True).select_related('category').first()
    if featured is None:
        featured = Post.objects.select_related('category').order_by('-pub_date').first()

    other_qs = Post.objects.select_related('category').order_by('-pub_date')
    if featured is not None:
        other_qs = other_qs.exclude(pk=featured.pk)
    others = list(other_qs[:6])

    index_strip = others[:3]
    recent = others[3:6] if len(others) >= 6 else others[:3]

    # Sidebar (cap at 4 per design hand-off). RightNowFeature is a singleton;
    # filter out the empty-state row so the template doesn't render a
    # half-blank "Right now" callout.
    bookshelf = list(BookshelfEntry.objects.all()[:4])
    right_now = (
        RightNowFeature.objects.filter(pk=1).exclude(book_title='').first()
    )

    return render(
        request,
        'posts/home.html',
        {
            'featured': featured,
            'index_strip': index_strip,
            'recent': recent,
            'bookshelf': bookshelf,
            'right_now': right_now,
        },
    )


def post_detail(request, slug):
    post = get_object_or_404(
        Post.objects.select_related('category').prefetch_related('tags'),
        slug=slug,
    )
    related = (
        Post.objects.select_related('category')
        .filter(category=post.category)
        .exclude(pk=post.pk)
        .order_by('-pub_date')[:2]
    )
    return render(
        request,
        'posts/post_detail.html',
        {'post': post, 'related': related},
    )


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts_qs = (
        Post.objects.select_related('category')
        .filter(category=category)
        .order_by('-pub_date')
    )
    page_obj, elided_range = _paginate(request, posts_qs)
    return render(
        request,
        'posts/category_detail.html',
        {'category': category, 'page_obj': page_obj, 'elided_range': elided_range},
    )


def tag_detail(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    posts_qs = (
        Post.objects.select_related('category')
        .filter(tags=tag)
        .order_by('-pub_date')
    )
    page_obj, elided_range = _paginate(request, posts_qs)
    return render(
        request,
        'posts/tag_detail.html',
        {'tag': tag, 'page_obj': page_obj, 'elided_range': elided_range},
    )


def _paginate(request, queryset):
    paginator = Paginator(queryset, POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    elided_range = paginator.get_elided_page_range(
        page_obj.number, on_each_side=2, on_ends=1
    )
    return page_obj, elided_range
