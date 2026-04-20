from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Post

POSTS_PER_PAGE = 10


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
    return render(request, 'posts/posts_detail.html', {'post': post})
