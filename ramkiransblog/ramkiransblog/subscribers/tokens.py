"""Signed tokens for email-link actions (confirm, unsubscribe).

We use Django's built-in signing module (no extra deps). Tokens are
HMAC-signed against SECRET_KEY, namespaced per action via salt, and
TimestampSigner-protected so we can expire them.

Usage:
    token = make_token(subscriber.id, action='confirm')
    sub_id = read_token(token, action='confirm', max_age_seconds=...)
"""
from django.core import signing


_SALTS = {
    'confirm': 'subscribers.confirm',
    'unsubscribe': 'subscribers.unsubscribe',
}


def make_token(subscriber_id: int, action: str) -> str:
    if action not in _SALTS:
        raise ValueError(f'Unknown token action: {action!r}')
    return signing.dumps(subscriber_id, salt=_SALTS[action])


def read_token(token: str, action: str, max_age_seconds: int) -> int:
    """Return the subscriber id encoded in the token, or raise.

    Raises:
        signing.BadSignature   — token tampered with or wrong action
        signing.SignatureExpired — token older than max_age_seconds
    """
    if action not in _SALTS:
        raise ValueError(f'Unknown token action: {action!r}')
    return signing.loads(token, salt=_SALTS[action], max_age=max_age_seconds)
