"""Resend SDK wrapper for transactional emails.

Why a wrapper:
- Centralizes the API-key + from-address handling
- Lets us mock send() in tests without import-time SDK calls
- Makes the eventual swap to AWS SES (or anything else) a one-file edit

Failure mode: send() never raises in production code paths. Failures are
logged so the signup flow doesn't 500 on the user just because Resend
is having a bad afternoon. The Subscriber row stays at confirmed=False,
which we can re-poke via a management command later.
"""
import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Subscriber
from .tokens import make_token

logger = logging.getLogger(__name__)


def _resend_client():
    """Lazy import + configure Resend so test envs don't need the API key."""
    import resend  # local import: keeps `resend` out of import time
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not api_key:
        return None
    resend.api_key = api_key
    return resend


def send_email(*, to: str, subject: str, html: str, text: str, reply_to: str | None = None) -> bool:
    """Send a transactional email via Resend. Returns True on success.

    Logs failures rather than raising — call sites should treat False as
    "we'll retry later" not "fail the user-facing flow."
    """
    client = _resend_client()
    if client is None:
        logger.warning('RESEND_API_KEY not set; skipping send to %s', to)
        return False

    from_addr = getattr(
        settings,
        'RESEND_FROM_EMAIL',
        f"Ram from {getattr(settings, 'SITE_NAME', 'the blog')} <onboarding@resend.dev>",
    )
    params = {
        'from': from_addr,
        'to': [to],
        'subject': subject,
        'html': html,
        'text': text,
    }
    if reply_to:
        params['reply_to'] = [reply_to]

    try:
        client.Emails.send(params)
        return True
    except Exception:  # noqa: BLE001 — Resend's SDK raises a wide variety
        logger.exception('Resend send failed for %s', to)
        return False


def send_confirmation_email(subscriber: Subscriber, request=None) -> bool:
    """Send the double-opt-in confirmation email."""
    token = make_token(subscriber.id, action='confirm')
    confirm_path = reverse('subscribe_confirm', args=[token])
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if request is not None and not site_url:
        site_url = f"{request.scheme}://{request.get_host()}"
    confirm_url = f"{site_url}{confirm_path}"

    context = {
        'subscriber': subscriber,
        'confirm_url': confirm_url,
        'site_name': getattr(settings, 'SITE_NAME', "Ramkiran's Blog"),
        'site_author': getattr(settings, 'SITE_AUTHOR', 'Ram Chevendra'),
        'physical_address': getattr(settings, 'MAIL_PHYSICAL_ADDRESS', ''),
    }

    html = render_to_string('subscribers/email/confirm.html', context)
    text = render_to_string('subscribers/email/confirm.txt', context)

    reply_to = getattr(settings, 'RESEND_REPLY_TO', '') or None

    return send_email(
        to=subscriber.email,
        subject=f"Confirm your subscription to {context['site_name']}",
        html=html,
        text=text,
        reply_to=reply_to,
    )
