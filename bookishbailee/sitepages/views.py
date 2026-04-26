from django.db.models import Count, Max
from django.shortcuts import render

from posts.models import Category, Post


def about(request):
    categories = (
        Category.objects.annotate(count=Count('posts'))
        .order_by('order', 'name')
    )
    aggregates = Post.objects.aggregate(
        total=Count('id'),
        latest=Max('pub_date'),
    )
    return render(
        request,
        'sitepages/about.html',
        {
            'categories': categories,
            'total_posts': aggregates['total'] or 0,
            'latest_post_date': aggregates['latest'],
            'category_count': categories.count(),
        },
    )
