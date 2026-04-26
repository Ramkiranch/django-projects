from .models import Category, WebConfig


def nav_categories(request):
    """Categories shown in the global nav and footer.

    Cached on the request so multiple template includes don't re-query.
    """
    return {'nav_categories': Category.objects.all()}


def feature_flags(request):
    """Expose `WebConfig` rows to templates as a `feature_flags` dict.

    Usage in templates:
        {% if feature_flags.show_subscriber_content %} ... {% endif %}

    Missing keys are falsy via Django's lenient dict lookup.
    """
    return {
        'feature_flags': dict(WebConfig.objects.values_list('key', 'enabled')),
    }
