"""Tests for the subscribers app.

Covers signup happy path, silent-on-duplicate behavior, honeypot rejection,
admin CSV export, signed-token roundtrip, confirm/unsubscribe view
behavior, and rate-limit enforcement on all three endpoints. Email
sending is patched out — we only verify that send is called with the
right subscriber, not that Resend actually delivers.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Subscriber
from .tokens import make_token, read_token


# Disable rate limiting for the existing happy-path / behavior tests.
# Each test fires only 1-2 requests, so the limit wouldn't trip
# anyway — but state from prior tests can leak via the cache, so we
# turn the decorator into a no-op for everything except RateLimitTests.

@override_settings(RATELIMIT_ENABLE=False)
@patch('subscribers.views.send_confirmation_email', return_value=True)
class SubscribeFormTests(TestCase):
    def test_valid_email_creates_subscriber(self, mock_send):
        response = self.client.post(reverse('subscribe'), {
            'email': 'reader@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subscriber.objects.filter(email='reader@example.com').exists())
        sub = Subscriber.objects.get(email='reader@example.com')
        self.assertEqual(sub.source, 'footer')
        self.assertFalse(sub.confirmed)  # double-opt-in: not confirmed yet
        mock_send.assert_called_once()

    def test_post_end_source_is_recorded(self, mock_send):
        self.client.post(reverse('subscribe'), {
            'email': 'reader2@example.com',
            'source': 'post-end',
            'website': '',
        })
        sub = Subscriber.objects.get(email='reader2@example.com')
        self.assertEqual(sub.source, 'post-end')

    def test_invalid_source_falls_back_to_footer(self, mock_send):
        self.client.post(reverse('subscribe'), {
            'email': 'reader3@example.com',
            'source': 'malicious-injected-value',
            'website': '',
        })
        sub = Subscriber.objects.get(email='reader3@example.com')
        self.assertEqual(sub.source, 'footer')

    def test_duplicate_unconfirmed_resends_confirmation(self, mock_send):
        Subscriber.objects.create(email='dup@example.com', source='footer', confirmed=False)
        response = self.client.post(reverse('subscribe'), {
            'email': 'dup@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Subscriber.objects.filter(email='dup@example.com').count(), 1)
        mock_send.assert_called_once()  # re-send for unconfirmed

    def test_duplicate_already_confirmed_does_not_resend(self, mock_send):
        Subscriber.objects.create(email='conf@example.com', source='footer', confirmed=True)
        response = self.client.post(reverse('subscribe'), {
            'email': 'conf@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        mock_send.assert_not_called()

    def test_honeypot_filled_silently_drops_submission(self, mock_send):
        response = self.client.post(reverse('subscribe'), {
            'email': 'bot@example.com',
            'source': 'footer',
            'website': 'https://spam.example.com',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Subscriber.objects.filter(email='bot@example.com').exists())
        mock_send.assert_not_called()

    def test_get_returns_405(self, mock_send):
        response = self.client.get(reverse('subscribe'))
        self.assertEqual(response.status_code, 405)

    def test_invalid_email_does_not_create_subscriber(self, mock_send):
        self.client.post(reverse('subscribe'), {
            'email': 'not-an-email',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(Subscriber.objects.count(), 0)
        mock_send.assert_not_called()


class TokenTests(TestCase):
    def test_token_roundtrip_returns_subscriber_id(self):
        token = make_token(42, action='confirm')
        self.assertEqual(read_token(token, action='confirm', max_age_seconds=3600), 42)

    def test_token_with_wrong_action_salt_fails(self):
        token = make_token(42, action='confirm')
        with self.assertRaises(signing.BadSignature):
            read_token(token, action='unsubscribe', max_age_seconds=3600)

    def test_expired_token_raises(self):
        token = make_token(42, action='confirm')
        with self.assertRaises(signing.SignatureExpired):
            # max_age=0 forces immediate expiration
            read_token(token, action='confirm', max_age_seconds=0)

    def test_unknown_action_raises_value_error(self):
        with self.assertRaises(ValueError):
            make_token(42, action='nonsense')


@override_settings(RATELIMIT_ENABLE=False)
class ConfirmViewTests(TestCase):
    def setUp(self):
        self.subscriber = Subscriber.objects.create(
            email='unconfirmed@example.com', source='footer', confirmed=False,
        )

    def test_valid_token_confirms_subscriber(self):
        token = make_token(self.subscriber.id, action='confirm')
        response = self.client.get(reverse('subscribe_confirm', args=[token]))
        self.assertEqual(response.status_code, 200)
        self.subscriber.refresh_from_db()
        self.assertTrue(self.subscriber.confirmed)
        self.assertContains(response, "You're in", status_code=200)

    def test_tampered_token_returns_400(self):
        response = self.client.get(reverse('subscribe_confirm', args=['not-a-real-token']))
        self.assertEqual(response.status_code, 400)
        self.subscriber.refresh_from_db()
        self.assertFalse(self.subscriber.confirmed)

    def test_token_for_missing_subscriber_returns_400(self):
        token = make_token(99999, action='confirm')
        response = self.client.get(reverse('subscribe_confirm', args=[token]))
        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_token_does_not_confirm(self):
        token = make_token(self.subscriber.id, action='unsubscribe')
        response = self.client.get(reverse('subscribe_confirm', args=[token]))
        self.assertEqual(response.status_code, 400)
        self.subscriber.refresh_from_db()
        self.assertFalse(self.subscriber.confirmed)

    def test_confirm_re_subscribes_unsubscribed_user(self):
        self.subscriber.unsubscribed = True
        self.subscriber.save()
        token = make_token(self.subscriber.id, action='confirm')
        self.client.get(reverse('subscribe_confirm', args=[token]))
        self.subscriber.refresh_from_db()
        self.assertTrue(self.subscriber.confirmed)
        self.assertFalse(self.subscriber.unsubscribed)


@override_settings(RATELIMIT_ENABLE=False)
class UnsubscribeViewTests(TestCase):
    def setUp(self):
        self.subscriber = Subscriber.objects.create(
            email='subscribed@example.com', source='footer', confirmed=True,
        )

    def test_valid_token_unsubscribes(self):
        token = make_token(self.subscriber.id, action='unsubscribe')
        response = self.client.get(reverse('subscribe_unsubscribe', args=[token]))
        self.assertEqual(response.status_code, 200)
        self.subscriber.refresh_from_db()
        self.assertTrue(self.subscriber.unsubscribed)

    def test_confirm_token_does_not_unsubscribe(self):
        token = make_token(self.subscriber.id, action='confirm')
        response = self.client.get(reverse('subscribe_unsubscribe', args=[token]))
        self.assertEqual(response.status_code, 400)
        self.subscriber.refresh_from_db()
        self.assertFalse(self.subscriber.unsubscribed)

    def test_already_unsubscribed_is_idempotent(self):
        self.subscriber.unsubscribed = True
        self.subscriber.save()
        token = make_token(self.subscriber.id, action='unsubscribe')
        response = self.client.get(reverse('subscribe_unsubscribe', args=[token]))
        self.assertEqual(response.status_code, 200)


@override_settings(RESEND_API_KEY='re_fake_key_for_tests')
class EmailSendTests(TestCase):
    """Verify our wrapper calls the Resend SDK with the right shape."""

    def test_send_confirmation_email_calls_resend(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target@example.com', source='footer')

        with patch('resend.Emails.send') as mock_send:
            ok = emails.send_confirmation_email(sub)

        self.assertTrue(ok)
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        params = args[0]
        self.assertEqual(params['to'], ['target@example.com'])
        self.assertIn('Confirm your subscription', params['subject'])
        # Both html + text bodies sent (multipart)
        self.assertIn('html', params)
        self.assertIn('text', params)
        # Body contains a confirm URL with /subscribe/confirm/ in it
        self.assertIn('/subscribe/confirm/', params['html'])
        self.assertIn('/subscribe/confirm/', params['text'])

    def test_send_returns_false_when_resend_raises(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target2@example.com', source='footer')

        with patch('resend.Emails.send', side_effect=Exception('boom')):
            ok = emails.send_confirmation_email(sub)

        self.assertFalse(ok)

    @override_settings(RESEND_API_KEY='')
    def test_send_returns_false_when_no_api_key(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target3@example.com', source='footer')
        ok = emails.send_confirmation_email(sub)
        self.assertFalse(ok)

    @override_settings(SITE_URL='http://localhost:8000', ALLOWED_HOSTS=['ramkiransblog.com'])
    def test_send_uses_request_host_not_misconfigured_site_url(self):
        """Regression: SITE_URL='http://localhost:8000' must not leak into
        production confirmation emails when a real HTTPS request is the
        source of the signup."""
        from django.test import RequestFactory
        from subscribers import emails

        sub = Subscriber.objects.create(email='target4@example.com', source='footer')
        request = RequestFactory().post(
            '/subscribe/',
            HTTP_HOST='ramkiransblog.com',
            **{'wsgi.url_scheme': 'https'},
        )

        with patch('resend.Emails.send') as mock_send:
            emails.send_confirmation_email(sub, request=request)

        params = mock_send.call_args[0][0]
        # Must use the request's host, NOT the misconfigured SITE_URL default
        self.assertIn('https://ramkiransblog.com/subscribe/confirm/', params['html'])
        self.assertIn('https://ramkiransblog.com/subscribe/confirm/', params['text'])
        self.assertNotIn('localhost', params['html'])
        self.assertNotIn('localhost', params['text'])

    @override_settings(SITE_URL='https://ramkiransblog.com')
    def test_send_falls_back_to_site_url_without_request(self):
        """Management-command / scheduled-job path: no request, use SITE_URL."""
        from subscribers import emails

        sub = Subscriber.objects.create(email='target5@example.com', source='footer')

        with patch('resend.Emails.send') as mock_send:
            emails.send_confirmation_email(sub)  # no request

        params = mock_send.call_args[0][0]
        self.assertIn('https://ramkiransblog.com/subscribe/confirm/', params['html'])

    @override_settings(SITE_URL='')
    def test_send_returns_false_without_request_or_site_url(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target6@example.com', source='footer')
        ok = emails.send_confirmation_email(sub)  # no request, empty SITE_URL
        self.assertFalse(ok)


@override_settings(RATELIMIT_ENABLE=True)
class RateLimitTests(TestCase):
    """End-to-end rate-limit checks. Cache must be cleared per-test.

    Note: Django's default LocMemCache is per-process. With multiple
    gunicorn workers in production the effective limit becomes
    `rate * num_workers` per IP per hour. For 5 workers that's still
    well under what a real bot would generate. If we need exact
    enforcement later, swap to Postgres- or Redis-backed cache.
    """

    def setUp(self):
        cache.clear()

    @patch('subscribers.views.send_confirmation_email', return_value=True)
    def test_subscribe_allows_first_five_then_blocks_sixth(self, _mock_send):
        url = reverse('subscribe')
        ip = '203.0.113.7'
        for i in range(5):
            response = self.client.post(
                url,
                {'email': f'r{i}@example.com', 'source': 'footer', 'website': ''},
                HTTP_X_FORWARDED_FOR=ip,
            )
            self.assertEqual(response.status_code, 302, f'request {i+1} should succeed')

        # 6th from same IP gets soft-blocked (302 + flash message), no row
        response = self.client.post(
            url,
            {'email': 'spammer@example.com', 'source': 'footer', 'website': ''},
            HTTP_X_FORWARDED_FOR=ip,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Subscriber.objects.filter(email='spammer@example.com').exists())
        # Inspect the flash message
        # (using follow=False; messages are queued in session)

    @patch('subscribers.views.send_confirmation_email', return_value=True)
    def test_different_ips_each_get_own_bucket(self, _mock_send):
        url = reverse('subscribe')
        for i in range(5):
            self.client.post(
                url,
                {'email': f'a{i}@example.com', 'source': 'footer', 'website': ''},
                HTTP_X_FORWARDED_FOR='203.0.113.10',
            )
        # Different IP — should still be allowed despite first IP being maxed
        response = self.client.post(
            url,
            {'email': 'fresh@example.com', 'source': 'footer', 'website': ''},
            HTTP_X_FORWARDED_FOR='203.0.113.11',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subscriber.objects.filter(email='fresh@example.com').exists())

    def test_confirm_blocks_at_eleventh_attempt(self):
        ip = '203.0.113.20'
        bad_token = 'tampered.payload.signature'  # any GET counts toward limit
        for i in range(10):
            response = self.client.get(
                reverse('subscribe_confirm', args=[bad_token]),
                HTTP_X_FORWARDED_FOR=ip,
            )
            # Each one returns 400 (invalid token) but counts toward rate
            self.assertEqual(response.status_code, 400, f'request {i+1}')
        # 11th hit triggers ratelimit (block=True) → 403
        response = self.client.get(
            reverse('subscribe_confirm', args=[bad_token]),
            HTTP_X_FORWARDED_FOR=ip,
        )
        self.assertEqual(response.status_code, 403)

    def test_unsubscribe_blocks_at_eleventh_attempt(self):
        ip = '203.0.113.30'
        bad_token = 'tampered.payload.signature'
        for i in range(10):
            response = self.client.get(
                reverse('subscribe_unsubscribe', args=[bad_token]),
                HTTP_X_FORWARDED_FOR=ip,
            )
            self.assertEqual(response.status_code, 400, f'request {i+1}')
        response = self.client.get(
            reverse('subscribe_unsubscribe', args=[bad_token]),
            HTTP_X_FORWARDED_FOR=ip,
        )
        self.assertEqual(response.status_code, 403)


@override_settings(RATELIMIT_ENABLE=False)
class PlausibleEventTests(TestCase):
    """Verify the Plausible 'Subscribed' custom-event script fires
    after a successful signup, but NOT on the home page itself."""

    @patch('subscribers.views.send_confirmation_email', return_value=True)
    def test_plausible_subscribed_event_fires_after_signup(self, _mock_send):
        # POST + follow the redirect so the message renders in the response
        response = self.client.post(
            reverse('subscribe'),
            {'email': 'evt@example.com', 'source': 'footer', 'website': ''},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("plausible('Subscribed')", body)

    def test_plausible_subscribed_event_not_on_plain_home_view(self):
        response = self.client.get(reverse('home'))
        body = response.content.decode()
        self.assertNotIn("plausible('Subscribed')", body)


@override_settings(RATELIMIT_ENABLE=False)
class CSVExportTests(TestCase):
    def setUp(self):
        Subscriber.objects.create(email='a@example.com', source='footer')
        Subscriber.objects.create(email='b@example.com', source='post-end')
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pwd-not-used')
        self.client.force_login(self.admin)

    def test_admin_csv_export_returns_csv(self):
        response = self.client.post(
            '/rk-admin/subscribers/subscriber/',
            {
                'action': 'export_as_csv',
                '_selected_action': [str(s.pk) for s in Subscriber.objects.all()],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode()
        self.assertIn('email,source,confirmed,unsubscribed,created_at', body)
        self.assertIn('a@example.com', body)
        self.assertIn('b@example.com', body)
