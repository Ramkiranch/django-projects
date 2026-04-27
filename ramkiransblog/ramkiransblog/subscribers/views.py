"""Newsletter signup view.

POST-only. Idempotent: re-submitting an existing email returns the same
"thanks" message rather than an error (we don't want to leak which
emails are subscribed). Honeypot-filled submissions return success
silently without writing anything to the DB.
"""
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .models import Subscriber

THANKS_MESSAGE = "Thanks — you're subscribed. I'll send updates when new posts go up."


@require_POST
def subscribe(request):
    form = SubscribeForm(request.POST)

    # Spam: pretend success, write nothing.
    if form.is_spam():
        messages.success(request, THANKS_MESSAGE)
        return _back(request)

    if form.is_valid():
        email = form.cleaned_data['email']
        source = request.POST.get('source', 'footer')
        # Source must match a valid choice; fall back silently.
        valid_sources = {choice[0] for choice in Subscriber.SOURCE_CHOICES}
        if source not in valid_sources:
            source = 'footer'
        # get_or_create avoids leaking "already subscribed" info.
        Subscriber.objects.get_or_create(
            email=email,
            defaults={'source': source},
        )
        messages.success(request, THANKS_MESSAGE)
    else:
        # Email validation failed — surface the error inline.
        for error in form.errors.get('email', []):
            messages.error(request, error)

    return _back(request)


def _back(request):
    """Redirect to the page the form was submitted from, or home."""
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return HttpResponseRedirect(referer)
    return HttpResponseRedirect(reverse('home'))
