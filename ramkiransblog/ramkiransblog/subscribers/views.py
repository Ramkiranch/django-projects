"""Newsletter signup views — subscribe, confirm (double-opt-in), unsubscribe.

Subscribe:
  POST /subscribe/  → creates a Subscriber row (or no-ops if email exists),
                      fires off a confirmation email, redirects back with
                      a flash message. Honeypot-filled submissions return
                      success silently without writing or sending.

Confirm:
  GET  /subscribe/confirm/<token>/  → flips Subscriber.confirmed=True if
                                       the signed token verifies.

Unsubscribe:
  GET  /subscribe/unsubscribe/<token>/  → flips Subscriber.unsubscribed=True.
"""
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .emails import send_confirmation_email
from .forms import SubscribeForm
from .models import Subscriber
from .ratelimit import client_ip
from .tokens import read_token

THANKS_MESSAGE = (
    "Thanks — almost there! Check your inbox for a confirmation link "
    "and click it to activate your subscription."
)
ALREADY_CONFIRMED_MESSAGE = "Thanks — you're already confirmed."
RATE_LIMITED_MESSAGE = (
    "Too many signup attempts from this address. Please try again later."
)

# 14 days. Long enough that someone who signs up before a long weekend
# can still confirm; short enough to expire stolen-link replays.
CONFIRM_TOKEN_MAX_AGE = 60 * 60 * 24 * 14
# Unsubscribe links don't expire in practice — they're in every broadcast
# email. 1 year is just a sanity bound.
UNSUBSCRIBE_TOKEN_MAX_AGE = 60 * 60 * 24 * 365


@ratelimit(key=client_ip, rate='5/h', method='POST', block=False)
@require_POST
def subscribe(request):
    # Soft block: surface a friendly flash message instead of a 403, so
    # legit users who happen to hit the limit (testing on their own site,
    # multiple family members behind the same NAT) get a clear UX rather
    # than an opaque error page.
    if getattr(request, 'limited', False):
        messages.error(request, RATE_LIMITED_MESSAGE)
        return _back(request)

    form = SubscribeForm(request.POST)

    # Spam: pretend success, write nothing.
    if form.is_spam():
        messages.success(request, THANKS_MESSAGE, extra_tags='subscribed')
        return _back(request)

    if form.is_valid():
        email = form.cleaned_data['email']
        source = request.POST.get('source', 'footer')
        valid_sources = {choice[0] for choice in Subscriber.SOURCE_CHOICES}
        if source not in valid_sources:
            source = 'footer'

        subscriber, created = Subscriber.objects.get_or_create(
            email=email,
            defaults={'source': source},
        )

        # Send confirmation only if (a) brand-new signup or
        # (b) existing row that hasn't yet confirmed (likely lost the
        # email or never opened it). Already-confirmed subscribers get
        # a different message and no extra email.
        if created or not subscriber.confirmed:
            send_confirmation_email(subscriber, request=request)
            messages.success(request, THANKS_MESSAGE, extra_tags='subscribed')
        else:
            messages.success(request, ALREADY_CONFIRMED_MESSAGE, extra_tags='subscribed')
    else:
        for error in form.errors.get('email', []):
            messages.error(request, error)

    return _back(request)


@ratelimit(key=client_ip, rate='10/h', method='GET', block=True)
def confirm(request, token: str):
    """Activate a subscription via the link in the confirmation email."""
    try:
        subscriber_id = read_token(token, action='confirm', max_age_seconds=CONFIRM_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return _invalid_token(request)

    try:
        subscriber = Subscriber.objects.get(pk=subscriber_id)
    except Subscriber.DoesNotExist:
        return _invalid_token(request)

    if not subscriber.confirmed:
        subscriber.confirmed = True
        subscriber.save(update_fields=['confirmed'])

    # If they had previously unsubscribed and re-confirmed, treat the
    # confirm action as also re-subscribing (they re-clicked a fresh
    # confirmation flow).
    if subscriber.unsubscribed:
        subscriber.unsubscribed = False
        subscriber.save(update_fields=['unsubscribed'])

    return render(request, 'subscribers/confirmed.html')


@ratelimit(key=client_ip, rate='10/h', method='GET', block=True)
def unsubscribe(request, token: str):
    """One-click unsubscribe from any broadcast email."""
    try:
        subscriber_id = read_token(token, action='unsubscribe', max_age_seconds=UNSUBSCRIBE_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return _invalid_token(request)

    try:
        subscriber = Subscriber.objects.get(pk=subscriber_id)
    except Subscriber.DoesNotExist:
        return _invalid_token(request)

    if not subscriber.unsubscribed:
        subscriber.unsubscribed = True
        subscriber.save(update_fields=['unsubscribed'])

    return render(request, 'subscribers/unsubscribed.html')


# -----------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------

def _back(request):
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return HttpResponseRedirect(referer)
    return HttpResponseRedirect(reverse('home'))


def _invalid_token(request):
    return render(request, 'subscribers/invalid_token.html', status=400)
