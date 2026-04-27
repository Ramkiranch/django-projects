"""Rate-limit key function that respects X-Forwarded-For from Caddy.

Django's REMOTE_ADDR sees the docker bridge IP (Caddy's container IP),
not the real client. Caddy is configured to set X-Forwarded-For to
the real client (see Caddyfile: `header_up X-Forwarded-For {remote_host}`).
We trust XFF here because Caddy strips/replaces inbound XFF headers
before forwarding — only the real client IP makes it through.

Use as: @ratelimit(key='subscribers.ratelimit.client_ip', rate='5/h', ...)
"""


def client_ip(group, request):
    """Return the real client IP for rate-limit bucketing."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        # Leftmost IP is the original client (multi-proxy chains comma-separate)
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')
